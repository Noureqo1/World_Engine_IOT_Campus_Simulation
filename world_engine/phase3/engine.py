"""Phase 3 Runtime: Digital Twin & Secure Fleet Simulation.

This engine extends Phase 2 with:
- Digital Twin asset hierarchy management
- Shadow state synchronization (Desired vs Reported)
- Secure OTA updates with SHA-256 verification
- Integration with Node-RED and ThingsBoard
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from world_engine.core.models import HVACMode, Room
from world_engine.utils.config import load_config
from world_engine.phase2.engine import HybridWorldEngine, HybridNode, Phase2Config

from world_engine.phase3.digital_twin import DigitalTwinManager, AssetMetadata
from world_engine.phase3.shadow_sync import ShadowSyncManager, ShadowState
from world_engine.phase3.ota_manager import OTAManager, OTAUpdate, OTAUpdateType

logger = logging.getLogger(__name__)

try:
    from gmqtt import Client as GMQTTClient
except ImportError:
    GMQTTClient = None


@dataclass(slots=True)
class Phase3Config:
    """Configuration for Phase 3 engine."""
    
    # Inherits from Phase 2
    phase2: Phase2Config
    
    # Phase 3 specific
    digital_twin_enabled: bool = True
    shadow_sync_enabled: bool = True
    ota_enabled: bool = True
    nodered_enabled: bool = True
    dashboard_enabled: bool = True
    
    # OTA configuration
    current_version: str = "1.0.0"
    ota_broadcast_topic: str = "campus/+/+/ota/config"
    
    # ThingsBoard configuration
    thingsboard_host: str = "thingsboard"
    thingsboard_port: int = 8080
    
    # Node-RED configuration
    nodered_host: str = "nodered"
    nodered_port: int = 1880
    
    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> "Phase3Config":
        phase3 = config.get("phase3", {})
        phase2 = Phase2Config.from_dict(config)
        
        digital_twin = phase3.get("digital_twin", {})
        thingsboard = digital_twin.get("thingsboard", {})
        nodered = phase3.get("nodered", {})
        ota = phase3.get("ota", {})
        
        return cls(
            phase2=phase2,
            digital_twin_enabled=phase3.get("digital_twin", {}).get("enabled", True),
            shadow_sync_enabled=phase3.get("shadow_sync", {}).get("enabled", True),
            ota_enabled=ota.get("enabled", True),
            nodered_enabled=nodered.get("enabled", True),
            dashboard_enabled=phase3.get("dashboard", {}).get("enabled", True),
            current_version=ota.get("current_version", "1.0.0"),
            ota_broadcast_topic=config.get("mqtt", {}).get("ota", {}).get("broadcast_topic", "campus/+/+/ota/config"),
            thingsboard_host=thingsboard.get("host", "thingsboard"),
            thingsboard_port=thingsboard.get("port", 8080),
            nodered_host=nodered.get("host", "nodered"),
            nodered_port=nodered.get("port", 1880),
        )


class Phase3WorldEngine:
    """Phase 3 engine extending Phase 2 with Digital Twin and OTA capabilities."""
    
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.phase3 = Phase3Config.from_dict(config)
        
        # Initialize Phase 2 hybrid engine
        self.hybrid_engine = HybridWorldEngine(config)
        
        # Initialize Phase 3 components
        self.digital_twin: Optional[DigitalTwinManager] = None
        self.shadow_sync: Optional[ShadowSyncManager] = None
        self.ota_manager: Optional[OTAManager] = None
        
        # OTA MQTT client for subscribing to updates
        self._ota_client: Optional[Any] = None
        self._ota_subscribed = False
        
        if self.phase3.digital_twin_enabled:
            self.digital_twin = DigitalTwinManager(config)
            logger.info("Digital Twin Manager initialized")
        
        if self.phase3.shadow_sync_enabled:
            self.shadow_sync = ShadowSyncManager(config)
            logger.info("Shadow Sync Manager initialized")
        
        if self.phase3.ota_enabled:
            self.ota_manager = OTAManager(config)
            logger.info("OTA Manager initialized")
    
    async def initialize(self) -> None:
        """Initialize all Phase 3 components with room data."""
        # Get all room IDs from Phase 2
        mqtt_nodes, coap_nodes = self.hybrid_engine.build_nodes()
        all_nodes = mqtt_nodes + coap_nodes
        room_ids = [node.room.room_id for node in all_nodes]
        
        # Initialize Phase 3 managers
        if self.shadow_sync:
            self.shadow_sync.initialize_for_rooms(room_ids)
        
        if self.ota_manager:
            self.ota_manager.initialize_for_rooms(room_ids)
        
        # Subscribe to OTA topics if enabled
        if self.phase3.ota_enabled and GMQTTClient:
            await self._subscribe_to_ota_topics()
        
        # Start background tasks
        if self.shadow_sync:
            await self.shadow_sync.start_background_sync()
        
        if self.ota_manager:
            await self.ota_manager.start_background_monitoring()
        
        logger.info(f"Phase 3 initialized for {len(room_ids)} rooms")
    
    async def _subscribe_to_ota_topics(self) -> None:
        """Subscribe to OTA update topics."""
        if not self.ota_manager or not GMQTTClient:
            return
        
        self._ota_client = GMQTTClient("phase3_ota_subscriber")
        
        def on_ota_connect(_client, _flags, _rc, _properties=None):
            logger.info("OTA MQTT client connected")
            # Subscribe to broadcast topic
            return _client.subscribe(self.phase3.ota_broadcast_topic, qos=1)
        
        async def on_ota_message(_client, topic, payload, _qos, _properties=None):
            """Handle incoming OTA update messages."""
            try:
                raw = payload.decode("utf-8") if isinstance(payload, (bytes, bytearray)) else str(payload)
                update_data = json.loads(raw)
                
                # Verify the update
                verification = self.ota_manager.verify_update(update_data)
                
                if not verification.success:
                    logger.error(f"OTA verification failed: {verification.error_message}")
                    return
                
                # Parse topic to determine target
                # Format: campus/{building}/{floor}/ota/config
                topic_parts = topic.split("/")
                if len(topic_parts) >= 4:
                    building = topic_parts[1]
                    floor = topic_parts[2]
                    
                    # Determine update type and target
                    if building == "+" and floor == "+":
                        update_type = OTAUpdateType.BROADCAST
                        target = None
                    elif floor == "+":
                        update_type = OTAUpdateType.TARGETED_BUILDING
                        target = building
                    else:
                        update_type = OTAUpdateType.TARGETED_FLOOR
                        target = f"{building}-{floor}"
                    
                    # Create update object
                    update = OTAUpdate(
                        update_id=update_data["update_id"],
                        update_type=update_type,
                        target=target,
                        version=update_data.get("version", self.phase3.current_version)
                    )
                    
                    # Apply to applicable rooms
                    mqtt_nodes, coap_nodes = self.hybrid_engine.build_nodes()
                    all_nodes = mqtt_nodes + coap_nodes
                    
                    for node in all_nodes:
                        if self.ota_manager.should_apply_update(node.room.room_id, update):
                            # Update physics parameters
                            if "alpha" in update_data:
                                node.room.k_env = update_data["alpha"]
                            if "beta" in update_data:
                                node.room.k_hvac = update_data["beta"]
                            if "k_env" in update_data:
                                node.room.k_env = update_data["k_env"]
                            if "k_hvac" in update_data:
                                node.room.k_hvac = update_data["k_hvac"]
                            
                            # Update version
                            self.ota_manager.apply_update(node.room.room_id, update)
                    
                    logger.info(f"OTA update {update.update_id} processed")
                
            except Exception as e:
                logger.error(f"Error processing OTA message: {e}")
        
        self._ota_client.on_connect = on_ota_connect
        self._ota_client.on_message = on_ota_message
        
        await self._ota_client.connect(
            self.phase3.phase2.mqtt_host,
            self.phase3.phase2.mqtt_port
        )
        self._ota_subscribed = True
        logger.info("Subscribed to OTA update topics")
    
    async def publish_shadow_state(self, node: HybridNode) -> None:
        """Publish shadow state updates to ThingsBoard via MQTT."""
        if not self.shadow_sync:
            return
        
        shadow = self.shadow_sync.get_shadow_state(node.room.room_id)
        if shadow:
            # Update reported state from current room state
            shadow.update_reported(
                hvac_mode=node.room.hvac_mode.name.lower(),
                lighting_dimmer=node.room.lighting_dimmer,
                target_temp=node.room.target_temp,
                version=self.ota_manager.get_device_version(node.room.room_id).current_version if self.ota_manager else None
            )
            
            # Check for pending commands
            pending = shadow.get_pending_commands()
            if pending:
                logger.info(f"{node.room.room_id}: Pending commands: {pending}")
                # Commands would be sent via the normal command pipeline
    
    async def publish_digital_twin_telemetry(self, node: HybridNode) -> None:
        """Publish telemetry with digital twin context."""
        # Get room metadata
        metadata = None
        if self.digital_twin:
            metadata = self.digital_twin.get_room_metadata(node.room.room_id)
        
        # Enhanced telemetry payload
        payload = node.room.to_telemetry_payload()
        
        if metadata:
            payload["metadata"]["room_info"] = metadata
        
        # Publish via Phase 2 mechanism
        # This would be integrated with the Phase 2 MQTT/CoAP publishing
    
    async def run(self) -> None:
        """Launch the Phase 3 runtime."""
        await self.initialize()
        
        logger.info(
            "Launching Phase 3: Digital Twin & Secure Fleet Simulation\n"
            f"  - Digital Twin: {self.phase3.digital_twin_enabled}\n"
            f"  - Shadow Sync: {self.phase3.shadow_sync_enabled}\n"
            f"  - OTA Updates: {self.phase3.ota_enabled}\n"
            f"  - Node-RED: {self.phase3.nodered_enabled}\n"
            f"  - Dashboard: {self.phase3.dashboard_enabled}"
        )
        
        # Run the Phase 2 hybrid engine
        await self.hybrid_engine.run()
    
    async def shutdown(self) -> None:
        """Stop all Phase 3 components and Phase 2 engine."""
        logger.info("Shutting down Phase 3 engine...")
        
        # Stop Phase 3 background tasks
        if self.shadow_sync:
            await self.shadow_sync.stop_background_sync()
        
        if self.ota_manager:
            await self.ota_manager.stop_background_monitoring()
        
        # Disconnect OTA MQTT client
        if self._ota_client and self._ota_subscribed:
            await self._ota_client.disconnect()
        
        # Shutdown Phase 2 engine
        await self.hybrid_engine.shutdown()
        
        logger.info("Phase 3 engine shutdown complete")
    
    def get_sync_report(self) -> dict[str, Any]:
        """Get shadow sync status report."""
        if self.shadow_sync:
            return self.shadow_sync.generate_sync_report()
        return {}
    
    def get_ota_statistics(self) -> dict[str, Any]:
        """Get OTA update statistics."""
        if self.ota_manager:
            return self.ota_manager.get_update_statistics()
        return {}
    
    def get_digital_twin_hierarchy(self) -> dict[str, Any]:
        """Get digital twin asset hierarchy."""
        if self.digital_twin:
            return self.digital_twin.export_to_thingsboard_format()
        return {}
    
    def export_provisioning_script(self, output_path: str = "provision_assets.py") -> None:
        """Export ThingsBoard asset provisioning script."""
        if self.digital_twin:
            self.digital_twin.save_provisioning_script(output_path)
            logger.info(f"Provisioning script exported to {output_path}")


def load_phase3_config(config_path: str = "config.phase3.yaml") -> dict[str, Any]:
    """Load a Phase 3 config file with fallback to Phase 2 and shared config."""
    path = Path(config_path)
    if path.exists():
        return load_config(str(path))
    
    # Fallback to Phase 2 config
    phase2_path = Path("config.phase2.yaml")
    if phase2_path.exists():
        return load_config(str(phase2_path))
    
    # Fallback to shared config
    return load_config("config.yaml")
