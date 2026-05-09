#!/usr/bin/env python3
"""
Update devices to mark 100 as active in ThingsBoard
"""

import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

THINGSBOARD_HOST = "localhost"
THINGSBOARD_PORT = 8080
USERNAME = "tenant@thingsboard.org"
PASSWORD = "tenant"

BASE_URL = f"http://{THINGSBOARD_HOST}:{THINGSBOARD_PORT}"

def login():
    """Authenticate with ThingsBoard."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": USERNAME, "password": PASSWORD}
    )
    response.raise_for_status()
    return response.json()["token"]

def update_device_attribute(token, device_id, attribute_name, attribute_value):
    """Update a device attribute."""
    response = requests.post(
        f"{BASE_URL}/api/plugins/telemetry/DEVICE/{device_id}/attributes/CLIENT_SCOPE",
        headers={"X-Authorization": f"Bearer {token}"},
        json={attribute_name: attribute_value}
    )
    if response.status_code == 200:
        logger.info(f"Set {attribute_name}={attribute_value} for device {device_id[:8]}...")
        return True
    else:
        logger.error(f"Failed to set attribute: {response.text}")
        return False

def update_device_server_attribute(token, device_id, attribute_name, attribute_value):
    """Update a device server-side attribute."""
    response = requests.post(
        f"{BASE_URL}/api/plugins/telemetry/DEVICE/{device_id}/attributes/SERVER_SCOPE",
        headers={"X-Authorization": f"Bearer {token}"},
        json={attribute_name: attribute_value}
    )
    if response.status_code == 200:
        logger.info(f"Set server attribute {attribute_name}={attribute_value} for device {device_id[:8]}...")
        return True
    else:
        logger.error(f"Failed to set server attribute: {response.text}")
        return False

def main():
    """Main function to update device active status."""
    try:
        token = login()
        logger.info("Authenticated with ThingsBoard")
        
        # Get all devices
        all_devices = []
        page = 0
        page_size = 100
        
        while True:
            devices = requests.get(
                f"{BASE_URL}/api/tenant/devices?pageSize={page_size}&page={page}",
                headers={"X-Authorization": f"Bearer {token}"}
            ).json()
            
            device_list = devices.get('data', [])
            if not device_list:
                break
                
            all_devices.extend(device_list)
            logger.info(f"Page {page}: {len(device_list)} devices")
            
            if len(device_list) < page_size:
                break
            page += 1
        
        logger.info(f"\nTotal devices: {len(all_devices)}")
        
        # Filter to RoomSensor devices (first 100)
        room_sensors = [d for d in all_devices if d['name'].startswith('Room-Sensor-')]
        room_sensors.sort(key=lambda x: int(x['name'].split('-')[2]))
        
        logger.info(f"Room-Sensor devices: {len(room_sensors)}")
        
        # Mark first 100 as active, rest as inactive
        active_count = 0
        inactive_count = 0
        
        for i, device in enumerate(room_sensors[:200], 1):
            device_id = device['id']['id']
            is_active = i <= 100
            
            if is_active:
                update_device_server_attribute(token, device_id, "active", True)
                update_device_server_attribute(token, device_id, "status", "active")
                active_count += 1
            else:
                update_device_server_attribute(token, device_id, "active", False)
                update_device_server_attribute(token, device_id, "status", "inactive")
                inactive_count += 1
        
        logger.info(f"\nUpdated {active_count} devices as active")
        logger.info(f"Updated {inactive_count} devices as inactive")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        raise

if __name__ == "__main__":
    main()
