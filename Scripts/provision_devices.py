#!/usr/bin/env python3
"""
ThingsBoard Device Provisioning Script
Creates 200 devices with 100 active
"""

import requests
import json
import logging
import time

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

def create_device(token, device_name, device_type="default"):
    """Create a device in ThingsBoard."""
    device_data = {
        "name": device_name,
        "type": device_type
    }
    response = requests.post(
        f"{BASE_URL}/api/device",
        headers={"X-Authorization": f"Bearer {token}"},
        json=device_data
    )
    if response.status_code == 200:
        logger.info(f"Created device: {device_name}")
        return response.json()
    elif response.status_code == 400 and "already exists" in response.text:
        logger.warning(f"Device {device_name} already exists")
        return None
    else:
        logger.error(f"Failed to create device {device_name}: {response.text}")
        return None

def get_device_credentials(token, device_id):
    """Get device credentials for MQTT connection."""
    response = requests.get(
        f"{BASE_URL}/api/device/{device_id}/credentials",
        headers={"X-Authorization": f"Bearer {token}"}
    )
    if response.status_code == 200:
        return response.json()
    else:
        logger.error(f"Failed to get credentials for device {device_id}")
        return None

def create_device_credentials(token, device_id, credential_type="ACCESS_TOKEN"):
    """Create device credentials for MQTT connection."""
    credentials_data = {
        "credentialsType": credential_type,
        "credentialsId": f"room_sensor_{device_id[:8]}"
    }
    response = requests.post(
        f"{BASE_URL}/api/device/{device_id}/credentials",
        headers={"X-Authorization": f"Bearer {token}"},
        json=credentials_data
    )
    if response.status_code == 200:
        logger.info(f"Created credentials for device {device_id}")
        return response.json()
    else:
        logger.error(f"Failed to create credentials for device {device_id}: {response.text}")
        return None

def save_device_info(device_info, credentials):
    """Save device information to a file."""
    with open("device_credentials.json", "a") as f:
        json.dump({
            "device_id": device_info["id"]["id"],
            "device_name": device_info["name"],
            "credentials_id": credentials["credentialsId"],
            "credentials_value": credentials["credentialsValue"]
        }, f)
        f.write("\n")

def main():
    """Main provisioning function."""
    try:
        token = login()
        logger.info("Successfully authenticated with ThingsBoard")
        
        # Clear existing credentials file
        open("device_credentials.json", "w").close()
        
        # Create 200 devices
        total_devices = 200
        active_devices = 100
        
        logger.info(f"Creating {total_devices} devices...")
        
        created_count = 0
        for i in range(1, total_devices + 1):
            device_name = f"Room-Sensor-{i:03d}"
            device_type = "RoomSensor" if i <= active_devices else "RoomSensorInactive"
            
            device = create_device(token, device_name, device_type)
            
            if device:
                device_id = device["id"]["id"]
                # Create credentials for the device
                credentials = create_device_credentials(token, device_id)
                if credentials:
                    save_device_info(device, credentials)
                    created_count += 1
            
            # Small delay to avoid overwhelming the API
            if i % 10 == 0:
                time.sleep(0.5)
        
        logger.info(f"Device provisioning completed. Created {created_count} devices.")
        logger.info(f"Active devices: {active_devices}")
        logger.info(f"Inactive devices: {total_devices - active_devices}")
        logger.info("Device credentials saved to device_credentials.json")
        
    except Exception as e:
        logger.error(f"Provisioning failed: {e}")
        raise

if __name__ == "__main__":
    main()
