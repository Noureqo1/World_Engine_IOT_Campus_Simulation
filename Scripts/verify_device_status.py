#!/usr/bin/env python3
"""
Verify device active status in ThingsBoard
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

def get_device_attributes(token, device_id):
    """Get device server-side attributes."""
    response = requests.get(
        f"{BASE_URL}/api/plugins/telemetry/DEVICE/{device_id}/attributes/SERVER_SCOPE",
        headers={"X-Authorization": f"Bearer {token}"}
    )
    if response.status_code == 200:
        return response.json()
    else:
        # Try CLIENT_SCOPE as fallback
        response = requests.get(
            f"{BASE_URL}/api/plugins/telemetry/DEVICE/{device_id}/attributes/CLIENT_SCOPE",
            headers={"X-Authorization": f"Bearer {token}"}
        )
        if response.status_code == 200:
            return response.json()
        return {}

def main():
    """Main function to verify device status."""
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
            
            if len(device_list) < page_size:
                break
            page += 1
        
        # Filter to RoomSensor devices
        room_sensors = [d for d in all_devices if d['name'].startswith('Room-Sensor-')]
        room_sensors.sort(key=lambda x: int(x['name'].split('-')[2]))
        
        logger.info(f"\nChecking first 10 Room-Sensor devices:")
        
        active_count = 0
        inactive_count = 0
        
        for device in room_sensors[:10]:
            device_id = device['id']['id']
            attrs = get_device_attributes(token, device_id)
            active = attrs.get('active', 'not set')
            status = attrs.get('status', 'not set')
            
            logger.info(f"{device['name']}: active={active}, status={status}")
            
            if active == True:
                active_count += 1
            elif active == False:
                inactive_count += 1
        
        logger.info(f"\nFirst 10 devices: {active_count} active, {inactive_count} inactive")
        
        # Check a device from the inactive range
        logger.info(f"\nChecking devices 101-110 (should be inactive):")
        for device in room_sensors[100:110]:
            device_id = device['id']['id']
            attrs = get_device_attributes(token, device_id)
            active = attrs.get('active', 'not set')
            status = attrs.get('status', 'not set')
            
            logger.info(f"{device['name']}: active={active}, status={status}")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        raise

if __name__ == "__main__":
    main()
