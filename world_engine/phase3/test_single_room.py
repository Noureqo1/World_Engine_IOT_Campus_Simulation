#!/usr/bin/env python3
"""
Test a single room simulator to verify connection
"""
import time
from room_simulator import RoomSimulator

def main():
    print("🏠 Testing single room simulator...")
    
    # Create one room simulator
    room = RoomSimulator("b01", "f01", "r001")
    
    print("⏳ Room simulator created. Waiting for connection...")
    
    # Run for 30 seconds to test
    for i in range(6):  # 6 * 5 = 30 seconds
        print(f"⏰ {i*5}s - Room temp: {room.temperature:.1f}°C, HVAC: {room.hvac_mode}")
        time.sleep(5)
    
    print("✅ Single room test completed")

if __name__ == "__main__":
    main()
