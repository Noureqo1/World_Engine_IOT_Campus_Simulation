"""
Room Model with Thermal Physics Simulation

This module defines the Room class which encapsulates:
- Room identification and MQTT topic generation
- Thermal physics simulation using a first-order heat transfer model
- State management for sensors and actuators
- Data validation against specification ranges
"""

import json
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# Sensor specification ranges for data validation
SENSOR_RANGES = {
    "temperature": (-40.0, 85.0),    # DHT22 spec range
    "humidity": (0.0, 100.0),         # Percentage
    "light_level": (0, 10000),        # Lux
    "lighting_dimmer": (0, 100),      # Percentage
}


class HVACMode(Enum):
    """HVAC operating modes with associated power levels."""
    OFF = 0.0
    ON = 1.0
    ECO = 0.5


@dataclass
class Room:
    """
    Represents a simulated IoT-enabled room with thermal physics.

    The thermal model follows:
    T_next = T_current + [k_env * (T_outside - T_current)] + [k_hvac * HVAC_power]

    Where:
    - k_env (0.01): Environmental heat transfer coefficient
    - k_hvac (0.2): HVAC effectiveness coefficient
    - HVAC_power: 1.0 (ON), 0.0 (OFF), 0.5 (ECO)

    Attributes:
        building: Building identifier (e.g., "b01")
        floor: Floor number (1-10)
        room_number: Room number on the floor (1-20)
    """
    building: str
    floor: int
    room_number: int
    protocol: str = "mqtt"

    # Physics coefficients (from config)
    k_env: float = 0.01
    k_hvac: float = 0.2
    outside_temp: float = 15.0

    # Sensor states
    temperature: float = field(default_factory=lambda: random.uniform(18.0, 26.0))
    humidity: float = field(default_factory=lambda: random.uniform(30.0, 60.0))
    occupancy: bool = field(default_factory=lambda: random.choice([True, False]))
    light_level: int = field(default_factory=lambda: random.randint(0, 1000))

    # Actuator states
    hvac_mode: HVACMode = HVACMode.OFF
    target_temp: float = 22.0
    lighting_dimmer: int = field(default_factory=lambda: random.randint(0, 100))

    def __post_init__(self) -> None:
        """Generate room ID and MQTT topic after initialization."""
        self._room_id: str | None = None
        self._mqtt_topic: str | None = None

    @property
    def room_id(self) -> str:
        """
        Generate unique room identifier.

        Format: "b01-f05-r202" (building-floor-room)
        """
        if self._room_id is None:
            self._room_id = f"{self.building}-f{self.floor:02d}-r{self.room_number:03d}"
        return self._room_id

    @property
    def mqtt_topic(self) -> str:
        """
        Generate MQTT topic path for telemetry publishing.

        Format: "campus/b01/floor_05/room_202/telemetry"
        """
        if self._mqtt_topic is None:
            self._mqtt_topic = (
                f"campus/{self.building}/floor_{self.floor:02d}/"
                f"room_{self.room_number:03d}/telemetry"
            )
        return self._mqtt_topic

    @property
    def phase2_mqtt_topic(self) -> str:
        """Generate the Phase 2 MQTT telemetry topic."""
        return f"campus/{self.building}/f{self.floor:02d}/r{self.room_number:03d}/telemetry"

    @property
    def phase2_command_topic(self) -> str:
        """Generate the Phase 2 MQTT command topic."""
        return f"campus/{self.building}/f{self.floor:02d}/r{self.room_number:03d}/cmd"

    @property
    def phase2_status_topic(self) -> str:
        """Generate the Phase 2 MQTT status topic."""
        return f"campus/{self.building}/f{self.floor:02d}/r{self.room_number:03d}/status"

    @property
    def phase2_coap_path(self) -> str:
        """Generate the Phase 2 CoAP resource path."""
        return f"/f{self.floor:02d}/r{self.room_number:03d}"

    @property
    def phase2_coap_telemetry_path(self) -> str:
        """Generate the Phase 2 CoAP telemetry resource path."""
        return f"/f{self.floor:02d}/r{self.room_number:03d}/telemetry"

    @property
    def phase2_coap_actuator_path(self) -> str:
        """Generate the Phase 2 CoAP actuator resource path."""
        return f"/f{self.floor:02d}/r{self.room_number:03d}/actuators/hvac"

    def update_physics(self) -> None:
        """
        Execute one physics simulation tick.

        Applies the thermal model formula:
        T_next = T_current + [k_env * (T_outside - T_current)] + [k_hvac * HVAC_power]

        Also simulates:
        - Humidity drift based on HVAC operation
        - Occupancy changes (random with low probability)
        - Light level changes based on occupancy
        """
        # Thermal physics calculation
        hvac_power = self.hvac_mode.value
        env_transfer = self.k_env * (self.outside_temp - self.temperature)

        # HVAC effect: positive when heating toward target, negative when cooling
        if self.temperature < self.target_temp:
            hvac_effect = self.k_hvac * hvac_power  # Heating
        else:
            hvac_effect = -self.k_hvac * hvac_power  # Cooling

        self.temperature += env_transfer + hvac_effect

        # Simple HVAC auto-control logic
        self._auto_hvac_control()

        # Humidity simulation (HVAC tends to dry air when running)
        if hvac_power > 0:
            self.humidity -= random.uniform(0.1, 0.3) * hvac_power
        else:
            # Natural humidity drift toward 50%
            self.humidity += 0.05 * (50.0 - self.humidity)

        # Clamp humidity to realistic bounds
        self.humidity = max(20.0, min(80.0, self.humidity))

        # Random occupancy changes (5% chance per tick)
        if random.random() < 0.05:
            self.occupancy = not self.occupancy

        # Light level follows occupancy with some noise
        if self.occupancy:
            target_light = 400 + random.randint(-50, 100)
            self.light_level = int(0.8 * self.light_level + 0.2 * target_light)
        else:
            self.light_level = max(0, self.light_level - random.randint(10, 30))

    def _auto_hvac_control(self) -> None:
        """
        Simple thermostat logic for HVAC mode selection.

        - OFF when within 0.5C of target
        - ECO when within 2C of target
        - ON when further than 2C from target
        """
        temp_diff = abs(self.temperature - self.target_temp)

        if temp_diff < 0.5:
            self.hvac_mode = HVACMode.OFF
        elif temp_diff < 2.0:
            self.hvac_mode = HVACMode.ECO
        else:
            self.hvac_mode = HVACMode.ON

    def to_telemetry_payload(self) -> dict[str, Any]:
        """
        Generate the JSON telemetry payload for MQTT publishing.

        Returns:
            Dictionary matching the exact required JSON structure
        """
        return {
            "metadata": {
                "sensor_id": self.room_id,
                "building": self.building,
                "floor": self.floor,
                "room": self.room_number,
                "timestamp": int(time.time())
            },
            "sensors": {
                "temperature": round(self.temperature, 2),
                "humidity": round(self.humidity, 2),
                "occupancy": self.occupancy,
                "light_level": self.light_level
            },
            "actuators": {
                "hvac_mode": self.hvac_mode.name.lower(),
                "lighting_dimmer": self.lighting_dimmer
            }
        }

    def to_json(self) -> str:
        """
        Serialize telemetry payload to JSON string.

        Returns:
            JSON string ready for MQTT publishing
        """
        return json.dumps(self.to_telemetry_payload())

    def get_db_state(self) -> dict[str, Any]:
        """
        Extract state for database persistence.

        Returns:
            Dictionary with fields matching room_states table schema
        """
        return {
            "room_id": self.room_id,
            "temp": round(self.temperature, 2),
            "humidity": round(self.humidity, 2),
            "hvac_mode": self.hvac_mode.name.lower(),
            "target_temp": self.target_temp,
            "timestamp": int(time.time())
        }

    def restore_from_state(self, state: dict[str, Any]) -> None:
        """
        Restore room state from database record.

        Args:
            state: Dictionary from get_room_state() database query
        """
        if not state:
            return

        self.temperature = state.get("last_temp", self.temperature)
        self.humidity = state.get("last_humidity", self.humidity)
        self.target_temp = state.get("target_temp", self.target_temp)

        hvac_mode_str = state.get("hvac_mode", "off").upper()
        try:
            self.hvac_mode = HVACMode[hvac_mode_str]
        except KeyError:
            self.hvac_mode = HVACMode.OFF

        logger.debug(
            f"{self.room_id}: Restored state - "
            f"temp={self.temperature:.1f}, hvac={self.hvac_mode.name}"
        )

    def validate_sensors(self) -> dict[str, bool]:
        """
        Validate sensor readings against specification ranges.

        Clamps out-of-range values and logs warnings.

        Returns:
            Dictionary indicating which sensors were in valid range
        """
        valid = {}

        # Temperature validation
        t_min, t_max = SENSOR_RANGES["temperature"]
        if self.temperature < t_min or self.temperature > t_max:
            logger.warning(
                f"{self.room_id}: Temperature {self.temperature:.2f} "
                f"out of range [{t_min}, {t_max}]"
            )
            self.temperature = max(t_min, min(t_max, self.temperature))
            valid["temperature"] = False
        else:
            valid["temperature"] = True

        # Humidity validation
        h_min, h_max = SENSOR_RANGES["humidity"]
        if self.humidity < h_min or self.humidity > h_max:
            logger.warning(
                f"{self.room_id}: Humidity {self.humidity:.2f} "
                f"out of range [{h_min}, {h_max}]"
            )
            self.humidity = max(h_min, min(h_max, self.humidity))
            valid["humidity"] = False
        else:
            valid["humidity"] = True

        # Light level validation
        l_min, l_max = SENSOR_RANGES["light_level"]
        if self.light_level < l_min or self.light_level > l_max:
            self.light_level = max(l_min, min(l_max, self.light_level))
            valid["light_level"] = False
        else:
            valid["light_level"] = True

        # Dimmer validation
        d_min, d_max = SENSOR_RANGES["lighting_dimmer"]
        if self.lighting_dimmer < d_min or self.lighting_dimmer > d_max:
            self.lighting_dimmer = max(d_min, min(d_max, self.lighting_dimmer))
            valid["lighting_dimmer"] = False
        else:
            valid["lighting_dimmer"] = True

        return valid

    def set_outside_temp(self, temp: float) -> None:
        """
        Update outside temperature (for night cycle simulation).

        Args:
            temp: New outside temperature in Celsius
        """
        self.outside_temp = temp


def create_campus_rooms(
    building_id: str = "b01",
    num_floors: int = 10,
    rooms_per_floor: int = 20,
    physics_config: dict | None = None
) -> list[Room]:
    """
    Factory function to create all rooms for a building.

    Args:
        building_id: Building identifier
        num_floors: Number of floors in the building
        rooms_per_floor: Number of rooms per floor
        physics_config: Optional physics coefficients

    Returns:
        List of Room instances (200 rooms for default config)
    """
    physics = physics_config or {}
    rooms = []

    for floor in range(1, num_floors + 1):
        for room_num in range(1, rooms_per_floor + 1):
            # Room numbers are floor * 100 + room position
            # e.g., Floor 5, Room 2 = Room 502
            actual_room_num = floor * 100 + room_num

            room = Room(
                building=building_id,
                floor=floor,
                room_number=actual_room_num,
                k_env=physics.get("k_env", 0.01),
                k_hvac=physics.get("k_hvac", 0.2),
                outside_temp=physics.get("outside_temp", 15.0)
            )
            rooms.append(room)

    return rooms
