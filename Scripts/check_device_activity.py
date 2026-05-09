#!/usr/bin/env python3
"""
Check device activity status in ThingsBoard
"""

import requests
import logging
from datetime import datetime

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

def get_device_latest_telemetry(token, device_id):
    """Get latest telemetry timestamps for a device."""
    response = requests.get(
        f"{BASE_URL}/api/plugins/telemetry/DEVICE/{device_id}/values/timeseries",
        headers={"X-Authorization": f"Bearer {token}"}
    )
    if response.status_code == 200:
        return response.json()
    else:
        return {}

def main():
    """Main function to check device activity."""
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
        
        # Check first 5 and devices 101-105
        logger.info("\n=== First 5 devices (should be active) ===")
        active_with_data = 0
        for device in room_sensors[:5]:
            device_id = device['id']['id']
            telemetry = get_device_latest_telemetry(token, device_id)
            
            if telemetry:
                # Get the latest timestamp from any key
                latest_ts = 0
                for key, values in telemetry.items():
                    if values and len(values) > 0:
                        ts = values[0].get('ts', 0)
                        if ts > latest_ts:
                            latest_ts = ts
                
                if latest_ts > 0:
                    active_with_data += 1
                    last_active = datetime.fromtimestamp(latest_ts / 1000)
                    logger.info(f"{device['name']}: Last activity at {last_active}")
                else:
                    logger.info(f"{device['name']}: No telemetry data")
            else:
                logger.info(f"{device['name']}: No telemetry data")
        
        logger.info(f"\nActive devices with telemetry: {active_with_data}/5")
        
        logger.info("\n=== Devices 101-105 (should be inactive) ===")
        inactive_with_data = 0
        for device in room_sensors[100:105]:
            device_id = device['id']['id']
            telemetry = get_device_latest_telemetry(token, device_id)
            
            if telemetry:
                inactive_with_data += 1
                logger.info(f"{device['name']}: Has telemetry data")
            else:
                logger.info(f"{device['name']}: No telemetry data")
        
        logger.info(f"\nInactive devices with telemetry: {inactive_with_data}/5")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        raise

if __name__ == "__main__":
    main()
