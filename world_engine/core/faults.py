"""
Fault Injection System for IoT Simulation

This module provides realistic fault modeling for IoT sensors and nodes.
Faults are configurable via probability settings and can be injected
per-room to simulate real-world sensor degradation and network issues.

Fault Types:
1. SENSOR_DRIFT   - Gradual bias accumulation in temperature readings
2. FROZEN_SENSOR  - Sensor stuck at last known value
3. TELEMETRY_DELAY - Network latency causing delayed message delivery
4. NODE_DROPOUT   - Complete node failure for a period of time
"""

import asyncio
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class FaultType(Enum):
    """Types of faults that can be injected into the simulation."""
    SENSOR_DRIFT = auto()      # Gradual temperature bias
    FROZEN_SENSOR = auto()     # Stuck sensor readings
    TELEMETRY_DELAY = auto()   # Network latency simulation
    NODE_DROPOUT = auto()      # Complete node failure


@dataclass
class FaultState:
    """
    Tracks the current fault state for a single room.

    Attributes:
        active_faults: Set of currently active fault types
        drift_bias: Accumulated temperature drift (Celsius)
        frozen_values: Dict of frozen sensor readings
        dropout_remaining: Ticks remaining in dropout period
        delay_seconds: Current telemetry delay amount
    """
    active_faults: set[FaultType] = field(default_factory=set)
    drift_bias: float = 0.0
    frozen_values: dict[str, float] = field(default_factory=dict)
    dropout_remaining: int = 0
    delay_seconds: float = 0.0


@dataclass
class FaultConfig:
    """
    Configuration for fault injection probabilities and parameters.

    All probabilities are per-tick chances (0.0 to 1.0).
    """
    enabled: bool = True

    # Probability of each fault type activating per tick
    sensor_drift_probability: float = 0.02      # 2% chance per tick
    frozen_sensor_probability: float = 0.01     # 1% chance per tick
    telemetry_delay_probability: float = 0.03   # 3% chance per tick
    node_dropout_probability: float = 0.005     # 0.5% chance per tick

    # Fault parameters
    drift_rate: float = 0.05          # Max drift per tick (Celsius)
    drift_max: float = 5.0            # Maximum accumulated drift
    dropout_min_ticks: int = 3        # Minimum dropout duration
    dropout_max_ticks: int = 20       # Maximum dropout duration
    delay_min: float = 0.5            # Minimum telemetry delay (seconds)
    delay_max: float = 3.0            # Maximum telemetry delay (seconds)

    # Recovery probabilities (per tick)
    drift_recovery_probability: float = 0.01    # Chance drift resets
    frozen_recovery_probability: float = 0.05   # Chance sensor unfreezes
    delay_recovery_probability: float = 0.1     # Chance delay clears

    @classmethod
    def from_dict(cls, config: dict) -> "FaultConfig":
        """Create FaultConfig from configuration dictionary."""
        return cls(
            enabled=config.get("enabled", True),
            sensor_drift_probability=config.get("sensor_drift_probability", 0.02),
            frozen_sensor_probability=config.get("frozen_sensor_probability", 0.01),
            telemetry_delay_probability=config.get("telemetry_delay_probability", 0.03),
            node_dropout_probability=config.get("node_dropout_probability", 0.005),
            drift_rate=config.get("drift_rate", 0.05),
            drift_max=config.get("drift_max", 5.0),
            dropout_min_ticks=config.get("dropout_min_ticks", 3),
            dropout_max_ticks=config.get("dropout_max_ticks", 20),
            delay_min=config.get("delay_min", 0.5),
            delay_max=config.get("delay_max", 3.0),
        )


class FaultInjector:
    """
    Manages fault injection for IoT room simulations.

    This class maintains fault states per room and provides methods
    to inject, update, and apply faults during simulation ticks.

    Usage:
        injector = FaultInjector(config)

        # Each tick:
        if injector.should_skip_tick(room_id):  # Check for dropout
            continue

        injector.update_faults(room_id)         # Roll for new faults
        temp = injector.apply_sensor_faults(room_id, actual_temp)

        delay = injector.get_telemetry_delay(room_id)
        if delay > 0:
            await asyncio.sleep(delay)
    """

    def __init__(self, config: FaultConfig | None = None):
        """
        Initialize the fault injector.

        Args:
            config: FaultConfig instance or None for defaults
        """
        self.config = config or FaultConfig()
        self._states: dict[str, FaultState] = {}

    def _get_state(self, room_id: str) -> FaultState:
        """Get or create fault state for a room."""
        if room_id not in self._states:
            self._states[room_id] = FaultState()
        return self._states[room_id]

    def update_faults(self, room_id: str) -> None:
        """
        Update fault states for a room (call once per tick).

        Rolls probability dice for each fault type and updates
        the room's fault state accordingly.

        Args:
            room_id: Unique room identifier
        """
        if not self.config.enabled:
            return

        state = self._get_state(room_id)

        # Update existing faults first
        self._update_existing_faults(state)

        # Roll for new faults
        self._roll_for_new_faults(state)

    def _update_existing_faults(self, state: FaultState) -> None:
        """Update and potentially recover from existing faults."""
        # Sensor drift recovery
        if FaultType.SENSOR_DRIFT in state.active_faults:
            if random.random() < self.config.drift_recovery_probability:
                state.active_faults.discard(FaultType.SENSOR_DRIFT)
                state.drift_bias = 0.0
            else:
                # Continue drifting
                drift_delta = random.uniform(-self.config.drift_rate, self.config.drift_rate)
                state.drift_bias += drift_delta
                state.drift_bias = max(-self.config.drift_max,
                                       min(self.config.drift_max, state.drift_bias))

        # Frozen sensor recovery
        if FaultType.FROZEN_SENSOR in state.active_faults:
            if random.random() < self.config.frozen_recovery_probability:
                state.active_faults.discard(FaultType.FROZEN_SENSOR)
                state.frozen_values.clear()

        # Telemetry delay recovery
        if FaultType.TELEMETRY_DELAY in state.active_faults:
            if random.random() < self.config.delay_recovery_probability:
                state.active_faults.discard(FaultType.TELEMETRY_DELAY)
                state.delay_seconds = 0.0

        # Node dropout countdown
        if state.dropout_remaining > 0:
            state.dropout_remaining -= 1
            if state.dropout_remaining == 0:
                state.active_faults.discard(FaultType.NODE_DROPOUT)

    def _roll_for_new_faults(self, state: FaultState) -> None:
        """Roll probability dice for new faults."""
        # Sensor drift
        if (FaultType.SENSOR_DRIFT not in state.active_faults and
                random.random() < self.config.sensor_drift_probability):
            state.active_faults.add(FaultType.SENSOR_DRIFT)
            state.drift_bias = random.uniform(-0.5, 0.5)  # Initial bias

        # Frozen sensor
        if (FaultType.FROZEN_SENSOR not in state.active_faults and
                random.random() < self.config.frozen_sensor_probability):
            state.active_faults.add(FaultType.FROZEN_SENSOR)
            # Frozen values will be captured on next apply

        # Telemetry delay
        if (FaultType.TELEMETRY_DELAY not in state.active_faults and
                random.random() < self.config.telemetry_delay_probability):
            state.active_faults.add(FaultType.TELEMETRY_DELAY)
            state.delay_seconds = random.uniform(
                self.config.delay_min, self.config.delay_max
            )

        # Node dropout
        if (FaultType.NODE_DROPOUT not in state.active_faults and
                random.random() < self.config.node_dropout_probability):
            state.active_faults.add(FaultType.NODE_DROPOUT)
            state.dropout_remaining = random.randint(
                self.config.dropout_min_ticks,
                self.config.dropout_max_ticks
            )

    def should_skip_tick(self, room_id: str) -> bool:
        """
        Check if room should skip this tick due to dropout.

        Args:
            room_id: Unique room identifier

        Returns:
            True if room is in dropout state and should skip
        """
        if not self.config.enabled:
            return False
        state = self._get_state(room_id)
        return FaultType.NODE_DROPOUT in state.active_faults

    def apply_sensor_faults(
        self,
        room_id: str,
        temperature: float,
        humidity: float
    ) -> tuple[float, float]:
        """
        Apply sensor faults to readings.

        Args:
            room_id: Unique room identifier
            temperature: Actual temperature reading
            humidity: Actual humidity reading

        Returns:
            Tuple of (faulted_temperature, faulted_humidity)
        """
        if not self.config.enabled:
            return temperature, humidity

        state = self._get_state(room_id)

        # Apply frozen sensor (returns last captured values)
        if FaultType.FROZEN_SENSOR in state.active_faults:
            if "temperature" in state.frozen_values:
                return (
                    state.frozen_values["temperature"],
                    state.frozen_values["humidity"]
                )
            else:
                # Capture current values as frozen
                state.frozen_values["temperature"] = temperature
                state.frozen_values["humidity"] = humidity
                return temperature, humidity

        # Apply sensor drift to temperature
        if FaultType.SENSOR_DRIFT in state.active_faults:
            temperature += state.drift_bias

        return temperature, humidity

    def get_telemetry_delay(self, room_id: str) -> float:
        """
        Get the telemetry delay for a room.

        Args:
            room_id: Unique room identifier

        Returns:
            Delay in seconds (0 if no delay fault active)
        """
        if not self.config.enabled:
            return 0.0
        state = self._get_state(room_id)
        if FaultType.TELEMETRY_DELAY in state.active_faults:
            return state.delay_seconds
        return 0.0

    def get_active_faults(self, room_id: str) -> list[str]:
        """
        Get list of active fault names for a room.

        Args:
            room_id: Unique room identifier

        Returns:
            List of fault type names
        """
        state = self._get_state(room_id)
        return [f.name.lower() for f in state.active_faults]

    def get_fault_summary(self) -> dict[str, Any]:
        """
        Get summary statistics of all faults across rooms.

        Returns:
            Dictionary with fault counts and affected rooms
        """
        summary = {
            "total_rooms": len(self._states),
            "faults": {
                "sensor_drift": 0,
                "frozen_sensor": 0,
                "telemetry_delay": 0,
                "node_dropout": 0
            },
            "affected_rooms": []
        }

        for room_id, state in self._states.items():
            if state.active_faults:
                summary["affected_rooms"].append(room_id)
                for fault in state.active_faults:
                    summary["faults"][fault.name.lower()] += 1

        return summary
