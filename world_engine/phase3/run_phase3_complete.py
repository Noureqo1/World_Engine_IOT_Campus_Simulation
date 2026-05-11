#!/usr/bin/env python3
"""
Complete Phase 3 Setup and Run Script
This script sets up and runs the complete Phase 3 IoT Campus Simulation
"""

import subprocess
import time
import threading
import sys
import os

def run_command(cmd, cwd=None):
    """Run a command and return the result"""
    try:
        result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def check_services():
    """Check if all services are running"""
    print("\n=== Checking Services ===")
    
    # Check Docker containers
    success, stdout, stderr = run_command("docker-compose -f docker-compose.phase3.yaml ps")
    if success:
        print("✓ Docker containers status:")
        print(stdout)
    else:
        print("✗ Error checking containers:", stderr)
    
    # Check ThingsBoard
    success, _, _ = run_command("curl -s http://localhost:8080/api/health")
    if success:
        print("✓ ThingsBoard is responding")
    else:
        print("✗ ThingsBoard not responding")
    
    # Check Node-RED
    success, _, _ = run_command("curl -s http://localhost:1880")
    if success:
        print("✓ Node-RED is responding")
    else:
        print("✗ Node-RED not responding")
    
    # Check MQTT
    success, _, _ = run_command("nc -z localhost 1883")
    if success:
        print("✓ MQTT broker is listening")
    else:
        print("✗ MQTT broker not responding")

def main():
    print("=== Phase 3 Complete IoT Campus Simulation ===")
    print("Starting setup and initialization...")
    
    # 1. Check if Docker containers are running
    print("\n1. Starting Docker containers...")
    success, stdout, stderr = run_command("docker-compose -f docker-compose.phase3.yaml up -d")
    if not success:
        print("✗ Failed to start containers:", stderr)
        return
    print("✓ Docker containers started")
    
    # Wait for services to be ready
    print("\n2. Waiting for services to be ready...")
    time.sleep(30)
    
    # 3. Build hierarchy in ThingsBoard
    print("\n3. Building ThingsBoard asset hierarchy...")
    success, stdout, stderr = run_command("python tb_setup/hierarchy_builder.py")
    if not success:
        print("✗ Failed to build hierarchy:", stderr)
    else:
        print("✓ Asset hierarchy built successfully")
    
    # 4. Provision devices
    print("\n4. Provisioning devices...")
    success, stdout, stderr = run_command("python provision_devices.py")
    if not success:
        print("✗ Failed to provision devices:", stderr)
    else:
        print("✓ Devices provisioned successfully")
    
    # 5. Activate first 100 devices
    print("\n5. Activating 100 devices...")
    success, stdout, stderr = run_command("python activate_devices.py")
    if not success:
        print("✗ Failed to activate devices:", stderr)
    else:
        print("✓ 100 devices activated successfully")
    
    # 6. Check services
    check_services()
    
    print("\n=== Setup Complete! ===")
    print("\nAccess Points:")
    print("- ThingsBoard: http://localhost:8080")
    print("  Username: tenant@thingsboard.org")
    print("  Password: tenant")
    print("- Node-RED: http://localhost:1880")
    print("\nNext Steps:")
    print("1. Import Node-RED flows from node_red/ directory")
    print("2. Run room simulators: python main_new.py")
    print("3. Send OTA updates: python ota_publisher.py --floor + --version 1.1")
    print("4. Monitor shadow sync: python shadow_sync.py")
    
    # Ask if user wants to start room simulators
    response = input("\nStart room simulators now? (y/n): ")
    if response.lower() == 'y':
        print("\n6. Starting room simulators...")
        print("This will start 400 room simulators (2 buildings × 10 floors × 20 rooms)")
        print("Press Ctrl+C to stop")
        
        try:
            # Run in background
            subprocess.Popen([sys.executable, "main_new.py"])
            print("✓ Room simulators started in background")
        except Exception as e:
            print(f"✗ Failed to start simulators: {e}")

if __name__ == "__main__":
    main()
