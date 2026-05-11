#!/usr/bin/env python3
"""
ThingsBoard Asset Provisioning Script for Phase 3 Digital Twin

This script provisions the hierarchical asset structure:
Campus -> Building -> Floor -> Room

Usage:
    python provision_thingsboard_assets.py [--host HOST] [--port PORT] [--user USERNAME] [--pass PASSWORD]
"""

import argparse
import json
import logging
import requests
import sys
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ThingsBoardProvisioner:
    """Provisions assets to ThingsBoard via REST API."""
    
    def __init__(self, host: str = "localhost", port: int = 9090, 
                 username: str = "tenant@thingsboard.org", password: str = "tenant"):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.base_url = f"http://{host}:{port}"
        self.token: Optional[str] = None
        self.asset_id_map: Dict[str, str] = {}
    
    def login(self) -> bool:
        """Authenticate with ThingsBoard."""
        try:
            response = requests.post(
                f"{self.base_url}/api/auth/login",
                json={"username": self.username, "password": self.password},
                timeout=10
            )
            response.raise_for_status()
            self.token = response.json()["token"]
            logger.info(f"Successfully authenticated with ThingsBoard at {self.base_url}")
            return True
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False
    
    def create_asset(self, asset_data: Dict) -> Optional[str]:
        """Create an asset in ThingsBoard."""
        try:
            response = requests.post(
                f"{self.base_url}/api/asset",
                headers={"X-Authorization": f"Bearer {self.token}"},
                json=asset_data,
                timeout=10
            )
            if response.status_code == 200:
                asset_id = response.json()["id"]["id"]
                logger.info(f"Created asset: {asset_data['name']} (ID: {asset_id})")
                return asset_id
            else:
                logger.error(f"Failed to create asset {asset_data['name']}: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error creating asset: {e}")
            return None
    
    def create_relation(self, from_id: str, to_id: str, relation_type: str = "Contains") -> bool:
        """Create a relation between assets."""
        try:
            response = requests.post(
                f"{self.base_url}/api/relation",
                headers={"X-Authorization": f"Bearer {self.token}"},
                json={
                    "from": {"entityType": "ASSET", "id": from_id},
                    "to": {"entityType": "ASSET", "id": to_id},
                    "type": relation_type
                },
                timeout=10
            )
            if response.status_code == 200:
                logger.info(f"Created relation: {from_id} -> {to_id} ({relation_type})")
                return True
            else:
                logger.error(f"Failed to create relation: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error creating relation: {e}")
            return False
    
    def set_server_attributes(self, asset_id: str, attributes: Dict) -> bool:
        """Set server-side attributes for an asset."""
        try:
            response = requests.post(
                f"{self.base_url}/api/plugins/telemetry/ASSET/{asset_id}/attributes/SERVER_SCOPE",
                headers={
                    "X-Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json"
                },
                json=attributes,
                timeout=10
            )
            if response.status_code == 200:
                logger.info(f"Set server attributes for asset {asset_id}")
                return True
            else:
                logger.error(f"Failed to set attributes for {asset_id}: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error setting attributes: {e}")
            return False
    
    def provision_campus_hierarchy(self) -> bool:
        """Provision the complete campus hierarchy."""
        campus_id = "ZC-Main-Campus"
        buildings = ["B01", "B02"]
        floors_per_building = 10
        rooms_per_floor = 20
        
        # Create Campus
        campus_asset_id = self.create_asset({
            "name": f"Campus {campus_id}",
            "type": "Campus"
        })
        if not campus_asset_id:
            return False
        self.asset_id_map[campus_id] = campus_asset_id
        
        # Create Buildings
        for building_id in buildings:
            building_asset_id = self.create_asset({
                "name": f"Building {building_id}",
                "type": "Building"
            })
            if not building_asset_id:
                continue
            self.asset_id_map[building_id] = building_asset_id
            
            # Create relation: Campus -> Building
            self.create_relation(campus_asset_id, building_asset_id, "Manages")
            
            # Create Floors
            for floor_num in range(1, floors_per_building + 1):
                floor_id = f"{building_id}-F{floor_num:02d}"
                floor_asset_id = self.create_asset({
                    "name": f"Floor {floor_num}",
                    "type": "Floor"
                })
                if not floor_asset_id:
                    continue
                self.asset_id_map[floor_id] = floor_asset_id
                
                # Create relation: Building -> Floor
                self.create_relation(building_asset_id, floor_asset_id, "Contains")
                
                # Create Rooms
                for room_num in range(1, rooms_per_floor + 1):
                    room_id = f"{building_id}-F{floor_num:02d}-R{room_num:03d}"
                    room_asset_id = self.create_asset({
                        "name": f"Room {room_num}",
                        "type": "Room"
                    })
                    if not room_asset_id:
                        continue
                    self.asset_id_map[room_id] = room_asset_id
                    
                    # Create relation: Floor -> Room
                    self.create_relation(floor_asset_id, room_asset_id, "Contains")
                    
                    # Set room metadata (server-side attributes)
                    self._set_room_metadata(room_asset_id, room_num, floor_num)
        
        logger.info(f"Provisioning complete: {len(self.asset_id_map)} assets created")
        return True
    
    def _set_room_metadata(self, asset_id: str, room_num: int, floor_num: int) -> None:
        """Generate and set random metadata for a room."""
        import random
        
        # Determine room type
        room_types = ["lecture_hall", "lab", "office", "corridor"]
        room_type = random.choice(room_types)
        
        # Generate coordinates
        room_index = room_num % 20 if room_num % 20 != 0 else 20
        row = (room_index - 1) // 5
        col = (room_index - 1) % 5
        
        base_x = 50 + col * 120
        base_y = 50 + row * 80
        
        # Generate metadata based on room type
        if room_type == "lecture_hall":
            square_footage = random.uniform(80, 100)
            occupant_capacity = random.randint(40, 50)
        elif room_type == "lab":
            square_footage = random.uniform(60, 80)
            occupant_capacity = random.randint(20, 35)
        elif room_type == "office":
            square_footage = random.uniform(30, 50)
            occupant_capacity = random.randint(2, 8)
        else:  # corridor
            square_footage = random.uniform(100, 150)
            occupant_capacity = random.randint(50, 100)
        
        metadata = {
            "square_footage": round(square_footage, 2),
            "occupant_capacity": occupant_capacity,
            "coordinates_x": round(base_x + random.uniform(-10, 10), 2),
            "coordinates_y": round(base_y + random.uniform(-10, 10), 2),
            "room_type": room_type
        }
        
        self.set_server_attributes(asset_id, metadata)
    
    def create_dashboard_widgets(self) -> bool:
        """Create dashboard widgets for visualization."""
        # This would create ThingsBoard dashboard entities
        # For now, we'll just log that this step would be performed
        logger.info("Dashboard widget creation would be performed here")
        logger.info("Recommended widgets:")
        logger.info("  - Image Map Widget for floor plan visualization")
        logger.info("  - Table Widget for sync status")
        logger.info("  - Cards Widget for OTA update status")
        return True
    
    def export_asset_map(self, filename: str = "asset_id_map.json") -> None:
        """Export the asset ID mapping to a file."""
        with open(filename, 'w') as f:
            json.dump(self.asset_id_map, f, indent=2)
        logger.info(f"Asset ID map exported to {filename}")


def main():
    """Main provisioning function."""
    parser = argparse.ArgumentParser(description="Provision ThingsBoard assets for Phase 3")
    parser.add_argument("--host", default="localhost", help="ThingsBoard host")
    parser.add_argument("--port", type=int, default=9090, help="ThingsBoard port")
    parser.add_argument("--user", default="tenant@thingsboard.org", help="Username")
    parser.add_argument("--password", default="tenant", help="Password")
    parser.add_argument("--export", default="asset_id_map.json", help="Export asset map to file")
    
    args = parser.parse_args()
    
    provisioner = ThingsBoardProvisioner(
        host=args.host,
        port=args.port,
        username=args.user,
        password=args.password
    )
    
    if not provisioner.login():
        logger.error("Failed to authenticate. Exiting.")
        sys.exit(1)
    
    if not provisioner.provision_campus_hierarchy():
        logger.error("Failed to provision assets. Exiting.")
        sys.exit(1)
    
    provisioner.create_dashboard_widgets()
    provisioner.export_asset_map(args.export)
    
    logger.info("Provisioning completed successfully!")


if __name__ == "__main__":
    main()
