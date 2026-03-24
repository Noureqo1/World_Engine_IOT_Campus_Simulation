import asyncio
import logging
import math
import random
import signal
import sys
import time
from pathlib import Path

import aiosqlite

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from world_engine.core.models import Room, create_campus_rooms
from world_engine.core.faults import FaultInjector, FaultConfig
from world_engine.core.health import FleetHealthMonitor, HealthConfig
from world_engine.db.db_setup import init_database, upsert_room_state, batch_commit, get_room_state
from world_engine.mqtt.publisher import get_mqtt_client
from world_engine.utils.config import load_config, get_default_config
from world_engine.utils.metrics import PerformanceMetrics, MetricsConfig


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("world_engine")


class NightCycleSimulator:

    def __init__(
        self,
        base_temp: float = 15.0,
        amplitude: float = 8.0,
        coldest_hour: int = 4,
        time_acceleration: float = 60.0
    ):
        self.base_temp = base_temp
        self.amplitude = amplitude
        self.coldest_hour = coldest_hour
        self.time_acceleration = time_acceleration
        self._start_time = time.time()

    def get_virtual_hour(self) -> float:
        """Get current virtual hour (0-24) based on accelerated time."""
        elapsed_real = time.time() - self._start_time
        elapsed_virtual = elapsed_real * self.time_acceleration
        virtual_hours = (elapsed_virtual / 3600) % 24
        return virtual_hours

    def get_outside_temp(self) -> float:
        """Calculate current outside temperature based on virtual time."""
        hour = self.get_virtual_hour()
        # Shift so coldest is at coldest_hour
        shifted_hour = hour - self.coldest_hour
        # Sinusoidal variation: coldest at coldest_hour, warmest 12 hours later
        temp = self.base_temp + self.amplitude * math.sin(
            2 * math.pi * (shifted_hour - 6) / 24
        )
        return round(temp, 2)


class WorldEngine:

    def __init__(self, config: dict):
        self.config = config
        self.rooms: list[Room] = []
        self.running = False
        self._tasks: list[asyncio.Task] = []
        self._shutdown_event = asyncio.Event()

        # Extract config values
        sim_config = config.get("simulation", {})
        self.tick_interval = sim_config.get("tick_interval", 5.0)
        self.jitter_max = sim_config.get("startup_jitter_max", 5.0)
        self.outside_temp = sim_config.get("outside_temperature", 15.0)
        self.time_acceleration = sim_config.get("time_acceleration", 60.0)

        # Night cycle config
        night_config = sim_config.get("night_cycle", {})
        self.night_cycle_enabled = night_config.get("enabled", True)
        self.night_cycle = NightCycleSimulator(
            base_temp=night_config.get("base_temp", self.outside_temp),
            amplitude=night_config.get("amplitude", 8.0),
            coldest_hour=night_config.get("coldest_hour", 4),
            time_acceleration=self.time_acceleration
        )

        # Initialize fault injector
        fault_config = FaultConfig.from_dict(config.get("faults", {}))
        self.fault_injector = FaultInjector(fault_config)

        # Initialize health monitor
        health_config = HealthConfig.from_dict(config.get("health", {}))
        self.health_monitor = FleetHealthMonitor(health_config)

        # Initialize metrics tracker
        metrics_config = MetricsConfig.from_dict(config.get("metrics", {}))
        self.metrics = PerformanceMetrics(metrics_config)

        # Database batch interval
        self.db_batch_interval = config.get("database", {}).get("batch_interval", 30)

    async def restore_room_states(self, db: aiosqlite.Connection) -> int:

        restored = 0
        for room in self.rooms:
            state = await get_room_state(db, room.room_id)
            if state:
                room.restore_from_state(state)
                restored += 1
        return restored

    def get_current_outside_temp(self) -> float:
        """Get current outside temperature (with night cycle if enabled)."""
        if self.night_cycle_enabled:
            return self.night_cycle.get_outside_temp()
        return self.outside_temp

    async def run_room_loop(
        self,
        room: Room,
        mqtt_client,
        db: aiosqlite.Connection
    ) -> None:
       
        # Register with health monitor
        self.health_monitor.register_room(room.room_id)

        # STARTUP JITTER: Random delay 0 to jitter_max seconds
        jitter = random.uniform(0, self.jitter_max)
        logger.debug(f"{room.room_id}: Starting with {jitter:.2f}s jitter")
        await asyncio.sleep(jitter)

        tick_count = 0

        while self.running and not self._shutdown_event.is_set():
            # Record start time for drift compensation
            tick_start = time.perf_counter()

            try:
                # === FAULT CHECK: Node Dropout ===
                self.fault_injector.update_faults(room.room_id)
                if self.fault_injector.should_skip_tick(room.room_id):
                    # Node is in dropout - skip this tick entirely
                    await asyncio.sleep(self.tick_interval)
                    continue

                # === UPDATE OUTSIDE TEMPERATURE (Night Cycle) ===
                room.set_outside_temp(self.get_current_outside_temp())

                # === PHYSICS UPDATE ===
                room.update_physics()

                # === DATA VALIDATION ===
                room.validate_sensors()

                # === APPLY SENSOR FAULTS ===
                faulted_temp, faulted_humidity = self.fault_injector.apply_sensor_faults(
                    room.room_id,
                    room.temperature,
                    room.humidity
                )

                # Create payload with potentially faulted values
                payload_data = room.to_telemetry_payload()
                payload_data["sensors"]["temperature"] = round(faulted_temp, 2)
                payload_data["sensors"]["humidity"] = round(faulted_humidity, 2)

                # Add fault info to payload if any faults active
                active_faults = self.fault_injector.get_active_faults(room.room_id)
                if active_faults:
                    payload_data["faults"] = active_faults

                # === TELEMETRY DELAY FAULT ===
                delay = self.fault_injector.get_telemetry_delay(room.room_id)
                if delay > 0:
                    await asyncio.sleep(delay)

                # === JSON SERIALIZATION ===
                import json
                payload = json.dumps(payload_data)

                # === MQTT PUBLISH ===
                await mqtt_client.publish(
                    room.mqtt_topic,
                    payload,
                    qos=0
                )

                # Record heartbeat and message for metrics
                self.health_monitor.record_heartbeat(room.room_id)
                self.metrics.record_message()

                # === DATABASE PERSISTENCE ===
                state = room.get_db_state()
                await upsert_room_state(
                    db,
                    state["room_id"],
                    state["temp"],
                    state["humidity"],
                    state["hvac_mode"],
                    state["target_temp"],
                    state["timestamp"]
                )

                tick_count += 1

            except asyncio.CancelledError:
                logger.debug(f"{room.room_id}: Cancelled, shutting down")
                raise
            except Exception as e:
                logger.error(f"{room.room_id}: Error in tick: {e}")

            # === PRECISION DRIFT COMPENSATION ===
            execution_time = time.perf_counter() - tick_start
            self.metrics.record_tick_latency(self.tick_interval, execution_time)

            adjusted_sleep = self.tick_interval - execution_time

            if adjusted_sleep > 0:
                await asyncio.sleep(adjusted_sleep)
            else:
                logger.warning(f"{room.room_id}: Tick overrun by {-adjusted_sleep:.3f}s")
                await asyncio.sleep(0)

    async def db_commit_loop(self, db: aiosqlite.Connection) -> None:

        while self.running and not self._shutdown_event.is_set():
            await asyncio.sleep(self.db_batch_interval)
            try:
                await batch_commit(db)
                logger.debug("Database batch commit complete")
            except asyncio.CancelledError:
                await batch_commit(db)
                raise
            except Exception as e:
                logger.error(f"Database commit error: {e}")

    async def stats_reporter(self) -> None:
        """Background task to report simulation statistics."""
        interval = 30
        while self.running and not self._shutdown_event.is_set():
            await asyncio.sleep(interval)

            if not self.rooms:
                continue

            temps = [r.temperature for r in self.rooms]
            avg_temp = sum(temps) / len(temps)
            occupied = sum(1 for r in self.rooms if r.occupancy)
            outside = self.get_current_outside_temp()
            virtual_hour = self.night_cycle.get_virtual_hour()

            # Fault summary
            fault_summary = self.fault_injector.get_fault_summary()
            faulted = len(fault_summary.get("affected_rooms", []))

            # Health summary
            health = self.health_monitor.get_summary_stats()

            logger.info(
                f"Stats: {len(self.rooms)} rooms | "
                f"Avg temp: {avg_temp:.1f}C | "
                f"Outside: {outside:.1f}C (hour {virtual_hour:.1f}) | "
                f"Occupied: {occupied} | "
                f"Faulted: {faulted} | "
                f"Health: {health['percentage']}%"
            )

    async def run(self, use_mock_mqtt: bool = False) -> None:

        self.running = True
        building_config = self.config.get("building", {})
        db_config = self.config.get("database", {})
        mqtt_config = self.config.get("mqtt", {})

        # Initialize database
        db_path = db_config.get("path", "world_engine.db")
        await init_database(db_path)

        # Create all 200 rooms
        logger.info("Creating room instances...")
        self.rooms = create_campus_rooms(
            building_id=building_config.get("id", "b01"),
            num_floors=building_config.get("floors", 10),
            rooms_per_floor=building_config.get("rooms_per_floor", 20),
            physics_config={
                "k_env": self.config.get("physics", {}).get("k_env", 0.01),
                "k_hvac": self.config.get("physics", {}).get("k_hvac", 0.2),
                "outside_temp": self.get_current_outside_temp()
            }
        )
        logger.info(f"Created {len(self.rooms)} rooms")

        # Open shared connections
        async with aiosqlite.connect(db_path) as db:
            # Restore previous state from database
            restored = await self.restore_room_states(db)
            if restored > 0:
                logger.info(f"Restored state for {restored} rooms from database")

            async with get_mqtt_client(
                broker_host=mqtt_config.get("broker_host", "localhost"),
                broker_port=mqtt_config.get("broker_port", 1883),
                client_id=mqtt_config.get("client_id_prefix", "world_engine"),
                use_mock=use_mock_mqtt
            ) as mqtt_client:

                logger.info(
                    f"Starting simulation: {len(self.rooms)} rooms, "
                    f"{self.tick_interval}s ticks, "
                    f"jitter 0-{self.jitter_max}s, "
                    f"night_cycle={self.night_cycle_enabled}"
                )

                # Create tasks for all rooms
                self._tasks = [
                    asyncio.create_task(
                        self.run_room_loop(room, mqtt_client, db),
                        name=f"room_{room.room_id}"
                    )
                    for room in self.rooms
                ]

                # Add utility tasks
                self._tasks.append(
                    asyncio.create_task(
                        self.db_commit_loop(db),
                        name="db_commit"
                    )
                )
                self._tasks.append(
                    asyncio.create_task(
                        self.stats_reporter(),
                        name="stats"
                    )
                )
                self._tasks.append(
                    asyncio.create_task(
                        self.health_monitor.run_health_check_loop(
                            mqtt_client, self._shutdown_event
                        ),
                        name="health_monitor"
                    )
                )
                self._tasks.append(
                    asyncio.create_task(
                        self.metrics.run_metrics_loop(
                            mqtt_client, self._shutdown_event
                        ),
                        name="metrics"
                    )
                )

                logger.info(f"Launched {len(self._tasks)} concurrent tasks")

                # Wait for shutdown signal
                try:
                    await self._shutdown_event.wait()
                except asyncio.CancelledError:
                    pass

                await self.shutdown()

    async def shutdown(self) -> None:
        """Gracefully shutdown all simulation tasks."""
        logger.info("Initiating graceful shutdown...")
        self.running = False
        self._shutdown_event.set()
        self.health_monitor.stop()
        self.metrics.stop()

        for task in self._tasks:
            task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        logger.info("Shutdown complete")


def setup_signal_handlers(engine: WorldEngine, loop: asyncio.AbstractEventLoop) -> None:
    """Setup signal handlers for graceful shutdown."""
    def handle_signal(sig):
        logger.info(f"Received signal {sig}, initiating shutdown...")
        engine._shutdown_event.set()

    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))


async def main():
    """Application entry point."""
    import os

    use_mock = "--mock" in sys.argv

    try:
        config = load_config("config.yaml")
        logger.info("Loaded config.yaml")
    except FileNotFoundError:
        logger.warning("config.yaml not found, using defaults")
        config = get_default_config()

    # Override MQTT settings from environment variables (for Docker)
    if os.environ.get("MQTT_HOST"):
        config.setdefault("mqtt", {})["broker_host"] = os.environ["MQTT_HOST"]
        logger.info(f"MQTT host overridden from env: {os.environ['MQTT_HOST']}")
    if os.environ.get("MQTT_PORT"):
        config.setdefault("mqtt", {})["broker_port"] = int(os.environ["MQTT_PORT"])
    if os.environ.get("DB_PATH"):
        config.setdefault("database", {})["path"] = os.environ["DB_PATH"]

    if use_mock:
        logger.info("Running in MOCK mode (no MQTT broker required)")

    engine = WorldEngine(config)

    loop = asyncio.get_running_loop()
    setup_signal_handlers(engine, loop)

    try:
        await engine.run(use_mock_mqtt=use_mock)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        await engine.shutdown()


if __name__ == "__main__":
    print("""
╔═══════════════════════════════════════════════════════════════╗
║               WORLD ENGINE v2.0 (Phase 1 Complete)            ║
║             IoT Campus Simulation - 200 Rooms                 ║
╠═══════════════════════════════════════════════════════════════╣
║  Features:                                                    ║
║    - Thermal physics simulation with night cycle              ║
║    - Fault injection (drift, freeze, delay, dropout)          ║
║    - Fleet health monitoring (60s heartbeat timeout)          ║
║    - Performance metrics (CPU, memory, latency)               ║
║    - State restoration from SQLite on restart                 ║
╠═══════════════════════════════════════════════════════════════╣
║  Usage:                                                       ║
║    python main.py          - Run with MQTT broker             ║
║    python main.py --mock   - Run without MQTT broker          ║
╚═══════════════════════════════════════════════════════════════╝
    """)
    asyncio.run(main())
