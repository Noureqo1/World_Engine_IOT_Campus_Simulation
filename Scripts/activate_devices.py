#!/usr/bin/env python3
"""
Send telemetry to ThingsBoard devices to make them appear active
"""

import requests
import json
import time
import random
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

def send_telemetry(token, device_id, telemetry_data):
    """Send telemetry data to a device."""
    response = requests.post(
        f"{BASE_URL}/api/plugins/telemetry/DEVICE/{device_id}/timeseries/values",
        headers={"X-Authorization": f"Bearer {token}"},
        json=telemetry_data
    )
    if response.status_code == 200:
        return True
    else:
        logger.error(f"Failed to send telemetry to {device_id[:8]}...: {response.text}")
        return False

def main():
    """Main function to activate devices."""
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
        
        # Filter to RoomSensor devices
        room_sensors = [d for d in all_devices if d['name'].startswith('Room-Sensor-')]
        room_sensors.sort(key=lambda x: int(x['name'].split('-')[2]))
        
        logger.info(f"\nTotal Room-Sensor devices: {len(room_sensors)}")
        
        # Send telemetry to first 100 devices
        active_count = 0
        for i, device in enumerate(room_sensors[:100], 1):
            device_id = device['id']['id']
            
            # Generate realistic telemetry data
            telemetry = {
                "temperature": round(random.uniform(18.0, 26.0), 2),
                "humidity": round(random.uniform(30.0, 60.0), 2),
                "light": round(random.uniform(100, 500), 2),
                "occupancy": random.randint(0, 10),
                "timestamp": int(time.time() * 1000)
            }
            
            if send_telemetry(token, device_id, telemetry):
                active_count += 1
                logger.info(f"{i}/100: Sent telemetry to {device['name']}")
            
            # Small delay to avoid overwhelming the API
            time.sleep(0.1)
        
        logger.info(f"\nSuccessfully sent telemetry to {active_count} devices")
        logger.info("These devices should now appear as 'active' in ThingsBoard")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        raise

if __name__ == "__main__":
    main()
