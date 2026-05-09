"""Phase 3: Edge-to-Cloud Integration - Digital Twin & Secure Fleet Simulation.

This module extends Phase 2 with:
- High-Fidelity Digital Twin with hierarchical asset model (Campus -> Building -> Floor -> Room)
- Shadow State Synchronization (Desired vs Reported states)
- Secure OTA Updates with SHA-256 verification
- Integration with Node-RED (IoT Gateway) and ThingsBoard (Digital Twin Platform)
"""

from world_engine.phase3.engine import Phase3WorldEngine, load_phase3_config
from world_engine.phase3.digital_twin import DigitalTwinManager, AssetMetadata
from world_engine.phase3.shadow_sync import ShadowSyncManager, ShadowState
from world_engine.phase3.ota_manager import OTAManager, OTAUpdate, OTAVerificationResult
from world_engine.phase3.room_simulator import RoomSimulator
from world_engine.phase3.ota_handler import OTAHandler
from world_engine.phase3.ota_publisher import OTAPublisher
from world_engine.phase3.main import main as run_phase3_main
from world_engine.phase3.run_phase3_complete import run_complete_phase3
from world_engine.phase3.test_mqtt_connection import test_mqtt_connection
from world_engine.phase3.test_single_room import test_single_room
from world_engine.phase3.main_phase3 import main as run_phase3_alternative

__all__ = [
    "Phase3WorldEngine",
    "load_phase3_config",
    "DigitalTwinManager",
    "AssetMetadata",
    "ShadowSyncManager",
    "ShadowState",
    "OTAManager",
    "OTAUpdate",
    "OTAVerificationResult",
    "RoomSimulator",
    "OTAHandler",
    "OTAPublisher",
    "run_phase3_main",
    "run_complete_phase3",
    "test_mqtt_connection",
    "test_single_room",
    "run_phase3_alternative",
]
