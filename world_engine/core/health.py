"""
Fleet Health Monitoring System

This module provides real-time health monitoring for the IoT fleet.
It tracks heartbeats from each room and flags rooms that go silent.

Features:
- Per-room heartbeat tracking
- Configurable timeout threshold (default 60 seconds)
- Fleet health summary publishing to MQTT
- Integration with fault injection system
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class HealthConfig:
    """Configuration for fleet health monitoring."""
    heartbeat_timeout: float = 60.0      # Seconds of silence = unhealthy
    check_interval: float = 10.0          # Seconds between health checks
    publish_interval: float = 30.0        # Seconds between health reports
    health_topic: str = "campus/fleet/health"

    @classmethod
    def from_dict(cls, config: dict) -> "HealthConfig":
        """Create HealthConfig from configuration dictionary."""
        return cls(
            heartbeat_timeout=config.get("heartbeat_timeout", 60.0),
            check_interval=config.get("check_interval", 10.0),
            publish_interval=config.get("publish_interval", 30.0),
        )


@dataclass
class RoomHealth:
    """Health state for a single room."""
    room_id: str
    last_heartbeat: float = field(default_factory=time.time)
    is_healthy: bool = True
    consecutive_misses: int = 0


class FleetHealthMonitor:
    """
    Monitors the health status of all rooms in the fleet.

    Tracks heartbeats from each room and identifies rooms that
    have gone silent (potential node failures or network issues).

    Usage:
        monitor = FleetHealthMonitor(config)

        # In room loop, report heartbeat after successful publish:
        monitor.record_heartbeat(room_id)

        # Background task checks health periodically:
        asyncio.create_task(monitor.run_health_check_loop(mqtt_client))
    """

    def __init__(self, config: HealthConfig | None = None):
        """
        Initialize the health monitor.

        Args:
            config: HealthConfig instance or None for defaults
        """
        self.config = config or HealthConfig()
        self._rooms: dict[str, RoomHealth] = {}
        self._running = False
        self._lock = asyncio.Lock()

    def register_room(self, room_id: str) -> None:
        """
        Register a room for health monitoring.

        Args:
            room_id: Unique room identifier
        """
        if room_id not in self._rooms:
            self._rooms[room_id] = RoomHealth(room_id=room_id)

    def record_heartbeat(self, room_id: str) -> None:
        """
        Record a heartbeat from a room.

        Call this after each successful telemetry publish.

        Args:
            room_id: Unique room identifier
        """
        if room_id not in self._rooms:
            self.register_room(room_id)

        room = self._rooms[room_id]
        room.last_heartbeat = time.time()
        room.is_healthy = True
        room.consecutive_misses = 0

    def check_health(self) -> dict[str, Any]:
        """
        Check health status of all rooms.

        Returns:
            Dictionary with health summary and lists of healthy/unhealthy rooms
        """
        now = time.time()
        healthy_rooms = []
        unhealthy_rooms = []

        for room_id, room in self._rooms.items():
            seconds_silent = now - room.last_heartbeat

            if seconds_silent > self.config.heartbeat_timeout:
                room.is_healthy = False
                room.consecutive_misses += 1
                unhealthy_rooms.append({
                    "room_id": room_id,
                    "silent_seconds": round(seconds_silent, 1),
                    "consecutive_misses": room.consecutive_misses
                })
            else:
                room.is_healthy = True
                healthy_rooms.append(room_id)

        return {
            "timestamp": int(now),
            "total_rooms": len(self._rooms),
            "healthy": len(healthy_rooms),
            "unhealthy": len(unhealthy_rooms),
            "unhealthy_rooms": unhealthy_rooms,
            "health_percentage": round(
                len(healthy_rooms) / max(1, len(self._rooms)) * 100, 1
            )
        }

    def get_unhealthy_rooms(self) -> list[str]:
        """
        Get list of currently unhealthy room IDs.

        Returns:
            List of room IDs that have exceeded heartbeat timeout
        """
        return [
            room_id for room_id, room in self._rooms.items()
            if not room.is_healthy
        ]

    def get_room_status(self, room_id: str) -> dict[str, Any] | None:
        """
        Get detailed health status for a specific room.

        Args:
            room_id: Unique room identifier

        Returns:
            Dictionary with room health details or None if not registered
        """
        room = self._rooms.get(room_id)
        if not room:
            return None

        now = time.time()
        return {
            "room_id": room_id,
            "is_healthy": room.is_healthy,
            "last_heartbeat": room.last_heartbeat,
            "seconds_since_heartbeat": round(now - room.last_heartbeat, 1),
            "consecutive_misses": room.consecutive_misses
        }

    async def run_health_check_loop(
        self,
        mqtt_client,
        shutdown_event: asyncio.Event | None = None
    ) -> None:
        """
        Background task that periodically checks fleet health.

        Args:
            mqtt_client: MQTT client for publishing health reports
            shutdown_event: Event to signal shutdown
        """
        self._running = True
        last_publish = 0

        logger.info(
            f"Health monitor started: timeout={self.config.heartbeat_timeout}s, "
            f"check_interval={self.config.check_interval}s"
        )

        while self._running:
            if shutdown_event and shutdown_event.is_set():
                break

            try:
                # Check health
                health_report = self.check_health()

                # Log warnings for unhealthy rooms
                if health_report["unhealthy"] > 0:
                    logger.warning(
                        f"Fleet health: {health_report['healthy']}/{health_report['total_rooms']} "
                        f"healthy ({health_report['health_percentage']}%)"
                    )
                    for room in health_report["unhealthy_rooms"][:5]:  # Log first 5
                        logger.warning(
                            f"  - {room['room_id']}: silent for {room['silent_seconds']}s"
                        )

                # Publish health report at configured interval
                now = time.time()
                if now - last_publish >= self.config.publish_interval:
                    payload = json.dumps(health_report)
                    try:
                        await mqtt_client.publish(
                            self.config.health_topic,
                            payload,
                            qos=1  # Use QoS 1 for health messages
                        )
                        logger.debug(f"Published health report to {self.config.health_topic}")
                    except Exception as e:
                        logger.error(f"Failed to publish health report: {e}")
                    last_publish = now

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")

            await asyncio.sleep(self.config.check_interval)

        logger.info("Health monitor stopped")

    def stop(self) -> None:
        """Signal the health check loop to stop."""
        self._running = False

    def get_summary_stats(self) -> dict[str, Any]:
        """
        Get summary statistics for logging/display.

        Returns:
            Dictionary with summary statistics
        """
        health = self.check_health()
        return {
            "total": health["total_rooms"],
            "healthy": health["healthy"],
            "unhealthy": health["unhealthy"],
            "percentage": health["health_percentage"]
        }
