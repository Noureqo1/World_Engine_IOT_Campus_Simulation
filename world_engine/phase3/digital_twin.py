"""Digital Twin Asset Hierarchy Management.

This module implements the hierarchical asset model:
Campus -> Building -> Floor -> Room

Each asset includes server-side metadata and relation mappings for data aggregation.
"""

import json
import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class AssetType(Enum):
    """Asset types in the digital twin hierarchy."""
    CAMPUS = "Campus"
    BUILDING = "Building"
    FLOOR = "Floor"
    ROOM = "Room"


class RoomType(Enum):
    """Room types for metadata classification."""
    LECTURE_HALL = "lecture_hall"
    LAB = "lab"
    OFFICE = "office"
    CORRIDOR = "corridor"


@dataclass
class AssetMetadata:
    """Server-side metadata for Room assets."""
    square_footage: float
    occupant_capacity: int
    coordinates_x: float
    coordinates_y: float
    room_type: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for ThingsBoard API."""
        return {
            "square_footage": self.square_footage,
            "occupant_capacity": self.occupant_capacity,
            "coordinates_x": self.coordinates_x,
            "coordinates_y": self.coordinates_y,
            "room_type": self.room_type
        }
    
    @classmethod
    def generate_random(cls, room_number: int, floor: int) -> "AssetMetadata":
        """Generate random metadata for a room."""
        room_type = random.choice(list(RoomType))
        
        # Generate coordinates based on room position
        # Each floor has 20 rooms, arranged in a grid
        room_index = room_number % 20 if room_number % 20 != 0 else 20
        row = (room_index - 1) // 5  # 4 rows of 5 rooms
        col = (room_index - 1) % 5   # 5 columns
        
        base_x = 50 + col * 120
        base_y = 50 + row * 80
        
        # Adjust based on room type
        if room_type == RoomType.LECTURE_HALL:
            square_footage = random.uniform(80, 100)
            occupant_capacity = random.randint(40, 50)
        elif room_type == RoomType.LAB:
            square_footage = random.uniform(60, 80)
            occupant_capacity = random.randint(20, 35)
        elif room_type == RoomType.OFFICE:
            square_footage = random.uniform(30, 50)
            occupant_capacity = random.randint(2, 8)
        else:  # CORRIDOR
            square_footage = random.uniform(100, 150)
            occupant_capacity = random.randint(50, 100)
        
        return cls(
            square_footage=round(square_footage, 2),
            occupant_capacity=occupant_capacity,
            coordinates_x=base_x + random.uniform(-10, 10),
            coordinates_y=base_y + random.uniform(-10, 10),
            room_type=room_type.value
        )


@dataclass
class Asset:
    """Represents an asset in the digital twin hierarchy."""
    asset_id: str
    asset_type: AssetType
    name: str
    parent_id: Optional[str] = None
    metadata: Optional[AssetMetadata] = None
    children: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for ThingsBoard API."""
        data = {
            "assetId": self.asset_id,
            "name": self.name,
            "type": self.asset_type.value,
        }
        if self.parent_id:
            data["parentId"] = self.parent_id
        if self.metadata:
            data["metadata"] = self.metadata.to_dict()
        return data


class DigitalTwinManager:
    """Manages the hierarchical digital twin asset structure."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.phase3_config = config.get("phase3", {})
        self.digital_twin_config = self.phase3_config.get("digital_twin", {})
        self.campus_config = config.get("campus", {})
        
        self.assets: Dict[str, Asset] = {}
        self._build_hierarchy()
    
    def _build_hierarchy(self) -> None:
        """Build the complete asset hierarchy: Campus -> Building -> Floor -> Room."""
        campus_id = self.campus_config.get("id", "ZC-Main-Campus")
        buildings = self.campus_config.get("buildings", ["B01"])
        floors_per_building = self.campus_config.get("floors_per_building", 10)
        rooms_per_floor = self.campus_config.get("rooms_per_floor", 20)
        
        # Create Campus asset
        campus = Asset(
            asset_id=campus_id,
            asset_type=AssetType.CAMPUS,
            name=f"Campus {campus_id}",
            parent_id=None
        )
        self.assets[campus_id] = campus
        logger.info(f"Created Campus asset: {campus_id}")
        
        # Create Building assets
        for building_id in buildings:
            building = Asset(
                asset_id=building_id,
                asset_type=AssetType.BUILDING,
                name=f"Building {building_id}",
                parent_id=campus_id
            )
            self.assets[building_id] = building
            campus.children.append(building_id)
            logger.info(f"Created Building asset: {building_id}")
            
            # Create Floor assets
            for floor_num in range(1, floors_per_building + 1):
                floor_id = f"{building_id}-F{floor_num:02d}"
                floor = Asset(
                    asset_id=floor_id,
                    asset_type=AssetType.FLOOR,
                    name=f"Floor {floor_num}",
                    parent_id=building_id
                )
                self.assets[floor_id] = floor
                building.children.append(floor_id)
                logger.info(f"Created Floor asset: {floor_id}")
                
                # Create Room assets
                for room_num in range(1, rooms_per_floor + 1):
                    room_id = f"{building_id}-F{floor_num:02d}-R{room_num:03d}"
                    metadata = AssetMetadata.generate_random(room_num, floor_num)
                    room = Asset(
                        asset_id=room_id,
                        asset_type=AssetType.ROOM,
                        name=f"Room {room_num}",
                        parent_id=floor_id,
                        metadata=metadata
                    )
                    self.assets[room_id] = room
                    floor.children.append(room_id)
        
        logger.info(f"Digital Twin hierarchy built: {len(self.assets)} assets total")
    
    def get_asset(self, asset_id: str) -> Optional[Asset]:
        """Get an asset by ID."""
        return self.assets.get(asset_id)
    
    def get_assets_by_type(self, asset_type: AssetType) -> List[Asset]:
        """Get all assets of a specific type."""
        return [asset for asset in self.assets.values() if asset.asset_type == asset_type]
    
    def get_children(self, asset_id: str) -> List[Asset]:
        """Get all child assets of a given asset."""
        asset = self.get_asset(asset_id)
        if not asset:
            return []
        return [self.assets[child_id] for child_id in asset.children if child_id in self.assets]
    
    def get_room_metadata(self, room_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific room."""
        asset = self.get_asset(room_id)
        if asset and asset.metadata:
            return asset.metadata.to_dict()
        return None
    
    def get_floor_rooms(self, floor_id: str) -> List[Asset]:
        """Get all rooms on a specific floor."""
        return self.get_children(floor_id)
    
    def calculate_floor_aggregate(self, floor_id: str, telemetry_data: Dict[str, Dict[str, float]]) -> Dict[str, float]:
        """Calculate aggregate telemetry for a floor from its rooms."""
        rooms = self.get_floor_rooms(floor_id)
        if not rooms:
            return {}
        
        # Collect all room telemetry
        room_temps = []
        room_humidity = []
        occupancy_count = 0
        
        for room in rooms:
            room_telemetry = telemetry_data.get(room.asset_id, {})
            if "temperature" in room_telemetry:
                room_temps.append(room_telemetry["temperature"])
            if "humidity" in room_telemetry:
                room_humidity.append(room_telemetry["humidity"])
            if "occupancy" in room_telemetry and room_telemetry["occupancy"]:
                occupancy_count += 1
        
        aggregates = {}
        if room_temps:
            aggregates["avg_temperature"] = round(sum(room_temps) / len(room_temps), 2)
            aggregates["min_temperature"] = round(min(room_temps), 2)
            aggregates["max_temperature"] = round(max(room_temps), 2)
        if room_humidity:
            aggregates["avg_humidity"] = round(sum(room_humidity) / len(room_humidity), 2)
        if rooms:
            aggregates["occupancy_rate"] = round(occupancy_count / len(rooms) * 100, 2)
        
        return aggregates
    
    def export_to_thingsboard_format(self) -> Dict[str, Any]:
        """Export the asset hierarchy in ThingsBoard API format."""
        return {
            "assets": [asset.to_dict() for asset in self.assets.values()],
            "relations": self._generate_relations()
        }
    
    def _generate_relations(self) -> List[Dict[str, Any]]:
        """Generate relation definitions for ThingsBoard."""
        relations = []
        for asset in self.assets.values():
            if asset.parent_id:
                relations.append({
                    "from": asset.parent_id,
                    "to": asset.asset_id,
                    "type": "Contains"
                })
        return relations
    
    def generate_provisioning_script(self, output_path: str = "provision_assets.py") -> str:
        """Generate a Python script to provision assets to ThingsBoard via REST API."""
        script = f'''#!/usr/bin/env python3
"""
ThingsBoard Asset Provisioning Script
Generated by Digital Twin Manager
"""

import requests
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

THINGSBOARD_HOST = "{self.digital_twin_config.get('thingsboard', {}).get('host', 'localhost')}"
THINGSBOARD_PORT = {self.digital_twin_config.get('thingsboard', {}).get('port', 8080)}
USERNAME = "{self.digital_twin_config.get('thingsboard', {}).get('username', 'tenant@thingsboard.org')}"
PASSWORD = "{self.digital_twin_config.get('thingsboard', {}).get('password', 'tenant')}"

BASE_URL = f"http://{{THINGSBOARD_HOST}}:{{THINGSBOARD_PORT}}"

def login():
    """Authenticate with ThingsBoard."""
    response = requests.post(
        f"{{BASE_URL}}/api/auth/login",
        json={{"username": USERNAME, "password": PASSWORD}}
    )
    response.raise_for_status()
    return response.json()["token"]

def create_asset(token, asset_data):
    """Create an asset in ThingsBoard."""
    response = requests.post(
        f"{{BASE_URL}}/api/asset",
        headers={{"X-Authorization": f"Bearer {{token}}"}},
        json=asset_data
    )
    if response.status_code == 200:
        logger.info(f"Created asset: {{asset_data['name']}}")
        return response.json()
    else:
        logger.error(f"Failed to create asset {{asset_data['name']}}: {{response.text}}")
        return None

def create_relation(token, from_id, to_id, relation_type):
    """Create a relation between assets."""
    response = requests.post(
        f"{{BASE_URL}}/api/relation",
        headers={{"X-Authorization": f"Bearer {{token}}"}},
        json={{
            "from": {{"entityType": "ASSET", "id": from_id}},
            "to": {{"entityType": "ASSET", "id": to_id}},
            "type": relation_type
        }}
    )
    if response.status_code == 200:
        logger.info(f"Created relation: {{from_id}} -> {{to_id}}")
    else:
        logger.error(f"Failed to create relation: {{response.text}}")

def set_server_attributes(token, asset_id, attributes):
    """Set server-side attributes for an asset."""
    response = requests.post(
        f"{{BASE_URL}}/api/plugins/telemetry/ASSET/{{asset_id}}/attributes/SERVER_SCOPE",
        headers={{"X-Authorization": f"Bearer {{token}}", "Content-Type": "application/json"}},
        json=attributes
    )
    if response.status_code == 200:
        logger.info(f"Set server attributes for {{asset_id}}")
    else:
        logger.error(f"Failed to set attributes for {{asset_id}}: {{response.text}}")

def main():
    """Main provisioning function."""
    try:
        token = login()
        logger.info("Successfully authenticated with ThingsBoard")
        
        # Load asset hierarchy
        hierarchy = {json.dumps(self.export_to_thingsboard_format(), indent=2)}
        
        # Create assets
        asset_id_map = {{}}
        for asset in hierarchy["assets"]:
            result = create_asset(token, asset)
            if result:
                asset_id_map[asset["assetId"]] = result["id"]["id"]
        
        # Create relations
        for relation in hierarchy["relations"]:
            from_id = asset_id_map.get(relation["from"])
            to_id = asset_id_map.get(relation["to"])
            if from_id and to_id:
                create_relation(token, from_id, to_id, relation["type"])
        
        # Set server attributes for rooms
        for asset in hierarchy["assets"]:
            if asset.get("type") == "Room" and asset.get("metadata"):
                asset_id = asset_id_map.get(asset["assetId"])
                if asset_id:
                    set_server_attributes(token, asset_id, asset["metadata"])
        
        logger.info("Asset provisioning completed successfully")
        
    except Exception as e:
        logger.error(f"Provisioning failed: {{e}}")
        raise

if __name__ == "__main__":
    main()
'''
        return script
    
    def save_provisioning_script(self, output_path: str = "provision_assets.py") -> None:
        """Save the provisioning script to a file."""
        script = self.generate_provisioning_script(output_path)
        with open(output_path, 'w') as f:
            f.write(script)
        logger.info(f"Provisioning script saved to {output_path}")
