#!/usr/bin/env python3
import requests

THINGSBOARD_HOST = "localhost"
THINGSBOARD_PORT = 8080
USERNAME = "tenant@thingsboard.org"
PASSWORD = "tenant"

BASE_URL = f"http://{THINGSBOARD_HOST}:{THINGSBOARD_PORT}"

def login():
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": USERNAME, "password": PASSWORD}
    )
    response.raise_for_status()
    return response.json()["token"]

def main():
    token = login()
    print("Authenticated with ThingsBoard")
    
    # Get all devices across all pages
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
        print(f"Page {page}: {len(device_list)} devices")
        
        if len(device_list) < page_size:
            break
        page += 1
    
    print(f"\nTotal devices retrieved: {len(all_devices)}")
    
    active = [d for d in all_devices if d['type'] == 'RoomSensor']
    inactive = [d for d in all_devices if d['type'] == 'RoomSensorInactive']
    other = [d for d in all_devices if d['type'] not in ['RoomSensor', 'RoomSensorInactive']]
    
    print(f"Active (RoomSensor): {len(active)}")
    print(f"Inactive (RoomSensorInactive): {len(inactive)}")
    print(f"Other types: {len(other)}")
    
    # List active devices
    print("\nActive devices:")
    for d in active[:10]:  # Show first 10
        print(f"  - {d['name']} (ID: {d['id']['id'][:8]}...)")
    if len(active) > 10:
        print(f"  ... and {len(active) - 10} more")

if __name__ == "__main__":
    main()
