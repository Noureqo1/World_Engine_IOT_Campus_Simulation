"""Secure OTA Update Management with SHA-256 Verification.

This module implements:
- Global and targeted OTA updates via MQTT
- SHA-256 hash verification for integrity
- Fleet versioning and reporting
- Audit logging for security events
"""

import hashlib
import json
import logging
import time
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class OTAStatus(Enum):
    """Status of OTA update process."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    VERIFYING = "verifying"
    APPLYING = "applying"
    SUCCESS = "success"
    FAILED = "failed"
    TAMPER_DETECTED = "tamper_detected"


class OTAUpdateType(Enum):
    """Type of OTA update."""
    BROADCAST = "broadcast"  # All devices
    TARGETED_BUILDING = "targeted_building"  # Specific building
    TARGETED_FLOOR = "targeted_floor"  # Specific floor
    TARGETED_ROOM = "targeted_room"  # Specific room


@dataclass
class OTAUpdate:
    """Represents an OTA update configuration."""
    update_id: str
    update_type: OTAUpdateType
    target: Optional[str] = None  # building_id, floor_id, or room_id
    version: str = "1.0.0"
    
    # Physics parameters to update
    alpha: Optional[float] = None
    beta: Optional[float] = None
    k_env: Optional[float] = None
    k_hvac: Optional[float] = None
    
    # Security
    hash: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    
    def calculate_hash(self) -> str:
        """Calculate SHA-256 hash of the update payload."""
        payload = {
            "update_id": self.update_id,
            "version": self.version,
        }
        if self.alpha is not None:
            payload["alpha"] = self.alpha
        if self.beta is not None:
            payload["beta"] = self.beta
        if self.k_env is not None:
            payload["k_env"] = self.k_env
        if self.k_hvac is not None:
            payload["k_hvac"] = self.k_hvac
        
        # Sort keys to ensure consistent hash
        payload_str = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(payload_str.encode()).hexdigest()
    
    def to_payload(self) -> Dict[str, Any]:
        """Convert to MQTT payload with hash."""
        if not self.hash:
            self.hash = self.calculate_hash()
        
        payload = {
            "update_id": self.update_id,
            "version": self.version,
            "timestamp": self.timestamp,
            "hash": self.hash,
        }
        
        if self.alpha is not None:
            payload["alpha"] = self.alpha
        if self.beta is not None:
            payload["beta"] = self.beta
        if self.k_env is not None:
            payload["k_env"] = self.k_env
        if self.k_hvac is not None:
            payload["k_hvac"] = self.k_hvac
        
        return payload
    
    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "OTAUpdate":
        """Create OTAUpdate from received payload."""
        update = cls(
            update_id=payload["update_id"],
            update_type=OTAUpdateType.BROADCAST,  # Will be determined by topic
            version=payload.get("version", "1.0.0"),
            hash=payload.get("hash"),
            timestamp=payload.get("timestamp", time.time())
        )
        
        if "alpha" in payload:
            update.alpha = payload["alpha"]
        if "beta" in payload:
            update.beta = payload["beta"]
        if "k_env" in payload:
            update.k_env = payload["k_env"]
        if "k_hvac" in payload:
            update.k_hvac = payload["k_hvac"]
        
        return update


@dataclass
class OTAVerificationResult:
    """Result of OTA update verification."""
    update_id: str
    success: bool
    status: OTAStatus
    error_message: Optional[str] = None
    calculated_hash: Optional[str] = None
    provided_hash: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "update_id": self.update_id,
            "success": self.success,
            "status": self.status.value,
            "error_message": self.error_message,
            "calculated_hash": self.calculated_hash,
            "provided_hash": self.provided_hash,
            "timestamp": self.timestamp
        }


@dataclass
class DeviceVersionInfo:
    """Version information for a device."""
    room_id: str
    current_version: str
    last_update_time: float
    update_history: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "room_id": self.room_id,
            "current_version": self.current_version,
            "last_update_time": datetime.fromtimestamp(self.last_update_time).isoformat(),
            "update_history": self.update_history
        }


class OTAManager:
    """Manages OTA updates for the IoT fleet."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.phase3_config = config.get("phase3", {})
        self.ota_config = self.phase3_config.get("ota", {})
        
        self.current_version = self.ota_config.get("current_version", "1.0.0")
        self.update_check_interval = self.ota_config.get("update_check_interval", 60)
        self.verification_config = self.ota_config.get("verification", {})
        self.algorithm = self.verification_config.get("algorithm", "sha256")
        self.max_retries = self.verification_config.get("max_retries", 3)
        self.updateable_parameters = self.ota_config.get("updateable_parameters", 
                                                       ["alpha", "beta", "k_env", "k_hvac"])
        
        self.device_versions: Dict[str, DeviceVersionInfo] = {}
        self.update_history: List[Dict[str, Any]] = []
        self.security_alerts: List[Dict[str, Any]] = []
        
        self._shutdown_event = asyncio.Event()
        self._update_task: Optional[asyncio.Task] = None
    
    def initialize_for_rooms(self, room_ids: List[str]) -> None:
        """Initialize version tracking for all rooms."""
        for room_id in room_ids:
            self.device_versions[room_id] = DeviceVersionInfo(
                room_id=room_id,
                current_version=self.current_version,
                last_update_time=time.time()
            )
        logger.info(f"Initialized OTA tracking for {len(room_ids)} devices")
    
    def create_broadcast_update(self, version: str, **params) -> OTAUpdate:
        """Create a broadcast update for all devices."""
        update_id = f"ota-{int(time.time())}-broadcast"
        update = OTAUpdate(
            update_id=update_id,
            update_type=OTAUpdateType.BROADCAST,
            version=version
        )
        
        for param in self.updateable_parameters:
            if param in params:
                setattr(update, param, params[param])
        
        update.hash = update.calculate_hash()
        logger.info(f"Created broadcast update: {update_id}, version {version}")
        return update
    
    def create_targeted_update(self, target: str, target_type: OTAUpdateType, 
                              version: str, **params) -> OTAUpdate:
        """Create a targeted update for specific building/floor/room."""
        update_id = f"ota-{int(time.time())}-{target_type.value}-{target}"
        update = OTAUpdate(
            update_id=update_id,
            update_type=target_type,
            target=target,
            version=version
        )
        
        for param in self.updateable_parameters:
            if param in params:
                setattr(update, param, params[param])
        
        update.hash = update.calculate_hash()
        logger.info(f"Created targeted update: {update_id} for {target}")
        return update
    
    def verify_update(self, payload: Dict[str, Any]) -> OTAVerificationResult:
        """Verify an OTA update payload using SHA-256."""
        update = OTAUpdate.from_payload(payload)
        
        # Recalculate hash
        calculated_hash = update.calculate_hash()
        provided_hash = payload.get("hash")
        
        if not provided_hash:
            return OTAVerificationResult(
                update_id=update.update_id,
                success=False,
                status=OTAStatus.FAILED,
                error_message="No hash provided in payload",
                calculated_hash=calculated_hash,
                provided_hash=provided_hash
            )
        
        if calculated_hash != provided_hash:
            # Security tampering detected
            alert = {
                "timestamp": datetime.now().isoformat(),
                "type": "TAMPERING_DETECTED",
                "update_id": update.update_id,
                "calculated_hash": calculated_hash,
                "provided_hash": provided_hash,
                "payload": payload
            }
            self.security_alerts.append(alert)
            logger.warning(f"OTA tampering detected: {update.update_id}")
            
            return OTAVerificationResult(
                update_id=update.update_id,
                success=False,
                status=OTAStatus.TAMPER_DETECTED,
                error_message="Hash mismatch - potential tampering",
                calculated_hash=calculated_hash,
                provided_hash=provided_hash
            )
        
        return OTAVerificationResult(
            update_id=update.update_id,
            success=True,
            status=OTAStatus.SUCCESS,
            calculated_hash=calculated_hash,
            provided_hash=provided_hash
        )
    
    def apply_update(self, room_id: str, update: OTAUpdate) -> bool:
        """Apply an OTA update to a specific device."""
        verification = self.verify_update(update.to_payload())
        
        if not verification.success:
            logger.error(f"Failed to apply update to {room_id}: {verification.error_message}")
            return False
        
        # Update device version
        device_info = self.device_versions.get(room_id)
        if device_info:
            device_info.current_version = update.version
            device_info.last_update_time = time.time()
            device_info.update_history.append(update.update_id)
        
        # Log update
        self.update_history.append({
            "timestamp": datetime.now().isoformat(),
            "update_id": update.update_id,
            "room_id": room_id,
            "version": update.version,
            "status": "success"
        })
        
        logger.info(f"Successfully applied update {update.update_id} to {room_id}")
        return True
    
    def get_device_version(self, room_id: str) -> Optional[DeviceVersionInfo]:
        """Get version information for a device."""
        return self.device_versions.get(room_id)
    
    def get_all_device_versions(self) -> List[Dict[str, Any]]:
        """Get version information for all devices."""
        return [info.to_dict() for info in self.device_versions.values()]
    
    def get_outdated_devices(self, target_version: str) -> List[Dict[str, Any]]:
        """Get devices that are not running the target version."""
        return [
            info.to_dict()
            for info in self.device_versions.values()
            if info.current_version != target_version
        ]
    
    def get_update_statistics(self) -> Dict[str, Any]:
        """Get statistics about OTA updates."""
        total = len(self.device_versions)
        if total == 0:
            return {}
        
        version_counts = {}
        for info in self.device_versions.values():
            version = info.current_version
            version_counts[version] = version_counts.get(version, 0) + 1
        
        latest_version = max(version_counts.keys()) if version_counts else self.current_version
        updated_count = version_counts.get(latest_version, 0)
        
        return {
            "total_devices": total,
            "latest_version": latest_version,
            "updated_count": updated_count,
            "pending_count": total - updated_count,
            "update_rate": round(updated_count / total * 100, 2),
            "version_distribution": version_counts,
            "total_updates": len(self.update_history),
            "security_alerts": len(self.security_alerts)
        }
    
    def get_security_alerts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent security alerts."""
        return self.security_alerts[-limit:]
    
    def clear_security_alerts(self) -> None:
        """Clear security alert history."""
        self.security_alerts.clear()
    
    async def start_background_monitoring(self) -> None:
        """Start background OTA monitoring task."""
        if self._update_task is None:
            self._update_task = asyncio.create_task(self._monitor_loop())
            logger.info("Background OTA monitoring started")
    
    async def stop_background_monitoring(self) -> None:
        """Stop background OTA monitoring task."""
        if self._update_task:
            self._shutdown_event.set()
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
            logger.info("Background OTA monitoring stopped")
    
    async def _monitor_loop(self) -> None:
        """Background task to monitor OTA status."""
        while not self._shutdown_event.is_set():
            try:
                # Check for devices that need updates
                stats = self.get_update_statistics()
                if stats.get("pending_count", 0) > 0:
                    logger.info(f"OTA Status: {stats['pending_count']} devices pending update")
                
                await asyncio.sleep(self.update_check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in OTA monitor loop: {e}")
                await asyncio.sleep(self.update_check_interval)
    
    def generate_mqtt_topic(self, update: OTAUpdate) -> str:
        """Generate MQTT topic for OTA update."""
        base_topic = "campus"
        
        if update.update_type == OTAUpdateType.BROADCAST:
            return f"{base_topic}/+/+/ota/config"
        elif update.update_type == OTAUpdateType.TARGETED_BUILDING:
            return f"{base_topic}/{update.target}/+/ota/config"
        elif update.update_type == OTAUpdateType.TARGETED_FLOOR:
            # Target format: "B01-F05"
            parts = update.target.split("-")
            if len(parts) == 2:
                return f"{base_topic}/{parts[0]}/{parts[1]}/ota/config"
        elif update.update_type == OTAUpdateType.TARGETED_ROOM:
            # Target format: "B01-F05-R012"
            parts = update.target.split("-")
            if len(parts) == 3:
                return f"{base_topic}/{parts[0]}/{parts[1]}/ota/config"
        
        return f"{base_topic}/+/+/ota/config"
    
    def should_apply_update(self, room_id: str, update: OTAUpdate) -> bool:
        """Determine if an update should be applied to a specific room."""
        if update.update_type == OTAUpdateType.BROADCAST:
            return True
        elif update.update_type == OTAUpdateType.TARGETED_BUILDING:
            return room_id.startswith(update.target)
        elif update.update_type == OTAUpdateType.TARGETED_FLOOR:
            return f"-{update.target}-" in room_id
        elif update.update_type == OTAUpdateType.TARGETED_ROOM:
            return room_id == update.target
        return False
