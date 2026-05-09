# Phase 3: Edge-to-Cloud Integration

This folder contains all Phase 3 Python modules organized in a clean structure.

## 📁 File Organization

### Core Modules
- **`engine.py`** - Main Phase3WorldEngine orchestrator
- **`digital_twin.py`** - Digital Twin asset hierarchy management
- **`shadow_sync.py`** - Shadow state synchronization manager
- **`ota_manager.py`** - OTA update management system

### Device Simulation
- **`room_simulator.py`** - Individual room device simulator
- **`config.py`** - Configuration settings for Phase 3

### OTA & Security
- **`ota_handler.py`** - SHA-256 verification and payload handling
- **`ota_publisher.py`** - OTA update publishing system

### Execution Scripts
- **`main.py`** - Simple room simulator launcher
- **`main_phase3.py`** - Alternative Phase 3 launcher
- **`run_phase3_complete.py`** - Complete Phase 3 orchestration script

### Testing & Utilities
- **`test_mqtt_connection.py`** - MQTT broker connection test
- **`test_single_room.py`** - Single room simulator test

### Package Structure
- **`__init__.py`** - Package initialization and exports

## 🚀 Usage Examples

### Basic Room Simulation
```python
from world_engine.phase3 import RoomSimulator, run_phase3_main

# Run single room
room = RoomSimulator("b01", "f01", "r001")
room.run()

# Run all rooms
run_phase3_main()
```

### Complete Phase 3 System
```python
from world_engine.phase3 import run_complete_phase3

# Run complete Phase 3 with Docker, ThingsBoard, and Node-RED
run_complete_phase3()
```

### Testing & Diagnostics
```python
from world_engine.phase3 import test_mqtt_connection, test_single_room

# Test MQTT broker connection
test_mqtt_connection()

# Test single room simulator
test_single_room()
```

### Digital Twin Management
```python
from world_engine.phase3 import DigitalTwinManager

dt = DigitalTwinManager()
dt.create_campus_hierarchy()
```

### OTA Updates
```python
from world_engine.phase3 import OTAPublisher

publisher = OTAPublisher()
publisher.publish_building_update("b01", new_config)
```

## 🔧 Dependencies

All modules use the shared configuration from `config.py`:
- MQTT Broker: localhost:1883
- ThingsBoard: http://localhost:8080
- Device hierarchy: 2 buildings × 10 floors × 20 rooms

## 📦 Integration

This package integrates with:
- **Node-RED** flows in `../node_red/`
- **ThingsBoard** dashboards and assets
- **Docker** containers for MQTT and ThingsBoard

## 🎯 Key Features

- **Hierarchical Digital Twin** (Campus → Building → Floor → Room)
- **Shadow State Synchronization** (Desired vs Reported)
- **Secure OTA Updates** with SHA-256 verification
- **Real-time Telemetry** and device simulation
- **Edge-to-Cloud Integration** with ThingsBoard
