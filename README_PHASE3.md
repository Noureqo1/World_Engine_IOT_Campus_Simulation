# Phase 3: Edge-to-Cloud Integration - Digital Twin & Secure Fleet Simulation

This phase extends the IoT campus simulation with professional digital twin capabilities, secure OTA updates, and edge-to-cloud integration using Node-RED and ThingsBoard.

## Overview

Phase 3 implements:
- **High-Fidelity Digital Twin**: Hierarchical asset model (Campus → Building → Floor → Room)
- **Shadow State Synchronization**: Desired vs Reported state management
- **Secure OTA Updates**: SHA-256 verified configuration updates
- **IoT Gateway Integration**: Node-RED as the edge gateway
- **Digital Twin Platform**: ThingsBoard for asset management and visualization

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Phase 3 Architecture                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ World Engine │    │   Node-RED   │    │ ThingsBoard  │      │
│  │  (Phase 3)   │───▶│   Gateway    │───▶│   Platform   │      │
│  │              │    │              │    │              │      │
│  │ - Digital    │    │ - Telemetry  │    │ - Asset      │      │
│  │   Twin       │    │   Processing │    │   Hierarchy  │      │
│  │ - Shadow     │    │ - OTA Verify │    │ - Dashboard  │      │
│  │   Sync       │    │ - Command    │    │ - Relations  │      │
│  │ - OTA Mgr    │    │   Routing    │    │ - Aggregates │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   HiveMQ     │    │   Redis      │    │ PostgreSQL   │      │
│  │   Broker     │    │   Cache      │    │   Database   │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Digital Twin Asset Hierarchy

**File**: `world_engine/phase3/digital_twin.py`

Implements a strict hierarchical model:
- **Campus**: Root asset (ZC-Main-Campus)
- **Buildings**: B01, B02
- **Floors**: 10 per building (B01-F01 through B01-F10)
- **Rooms**: 20 per floor (B01-F01-R001 through B01-F01-R020)

**Room Metadata (Server-Side Attributes)**:
- `square_footage`: Room area in square feet
- `occupant_capacity`: Maximum occupancy
- `coordinates_x`, `coordinates_y`: Position on floor plan
- `room_type`: lecture_hall, lab, office, corridor

**Features**:
- Asset relation mapping for data aggregation
- Floor-level telemetry aggregation (avg temperature, humidity, occupancy)
- ThingsBoard provisioning script generation

### 2. Shadow State Synchronization

**File**: `world_engine/phase3/shadow_sync.py`

Implements the AWS IoT Shadow pattern:
- **Desired State**: Set by administrators via dashboard (Shared Attributes)
- **Reported State**: Actual current status from nodes (Client Attributes)
- **Reconciliation**: Automatic sync on heartbeat

**Sync Status**:
- `SYNCED`: Desired and reported states match
- `OUT_OF_SYNC`: Minor differences (1-2 attributes)
- `CONFLICT`: Major differences (3+ attributes)
- `PENDING`: Update in progress

**Tracked Attributes**:
- `hvac_mode`: HVAC operating mode
- `lighting_dimmer`: Light level (0-100)
- `target_temp`: Target temperature

### 3. Secure OTA Updates

**File**: `world_engine/phase3/ota_manager.py`

Implements secure over-the-air updates:
- **Global Updates**: Broadcast to all 200 devices
- **Targeted Updates**: By building, floor, or specific room
- **SHA-256 Verification**: Cryptographic integrity checking
- **Fleet Versioning**: Track update status across all devices

**Updateable Parameters**:
- `alpha`: Thermal leakage coefficient
- `beta`: Heat capacity coefficient
- `k_env`: Environmental heat transfer
- `k_hvac`: HVAC effectiveness

**Security Features**:
- SHA-256 hash calculation with sorted JSON keys
- Tamper detection with security alerts
- Audit logging for all update attempts

### 4. Node-RED IoT Gateway

**File**: `flows/phase3_gateway.json`

Node-RED flow implementing:
- **Telemetry Processing**: Parse and enrich incoming sensor data
- **Floor Aggregation**: Calculate floor-level averages
- **Command Routing**: Forward dashboard commands to devices
- **OTA Verification**: SHA-256 hash verification at the edge
- **Shadow Sync**: Compare desired vs reported states

**MQTT Topics**:
- `campus/+/+/+/telemetry`: Incoming telemetry
- `campus/+/+/+/cmd`: Command messages
- `campus/+/+/ota/config`: OTA updates
- `campus/+/+/+/shadow`: Shadow state updates

### 5. ThingsBoard Integration

**File**: `provision_thingsboard_assets.py`

Provisions the complete asset hierarchy to ThingsBoard:
- Creates Campus, Building, Floor, and Room assets
- Sets up "Contains" and "Manages" relations
- Configures server-side attributes for rooms
- Generates asset ID mapping

**Dashboard Widgets** (recommended):
- **Image Map Widget**: Floor plan with room polygons
- **Table Widget**: Sync status for all 200 devices
- **Cards Widget**: OTA update status
- **Chart Widget**: Temperature heatmap visualization

## Setup Instructions

### Prerequisites

- Docker and Docker Compose
- Python 3.9+
- MQTT client (optional, for testing)

### Quick Start

1. **Start the Phase 3 stack**:
   ```bash
   docker-compose -f docker-compose.phase3.yaml up -d
   ```

2. **Wait for services to be ready** (approx. 2-3 minutes):
   ```bash
   docker-compose -f docker-compose.phase3.yaml ps
   ```

3. **Provision ThingsBoard assets**:
   ```bash
   python provision_thingsboard_assets.py --host localhost --port 9090
   ```

4. **Run the Phase 3 World Engine**:
   ```bash
   python -m world_engine.phase3.engine
   ```

### Access Points

- **Node-RED**: http://localhost:1880
- **ThingsBoard**: http://localhost:8080
  - Default tenant: `tenant@thingsboard.org`
  - Default password: `tenant`
- **HiveMQ WebSocket**: ws://localhost:8000/mqtt
- **World Engine Logs**: `docker logs world-engine-phase3`

## Configuration

Edit `config.phase3.yaml` to customize:

```yaml
phase3:
  digital_twin:
    thingsboard:
      host: "thingsboard"
      port: 9090
  
  shadow_sync:
    enabled: true
    sync_check_interval: 10
  
  ota:
    enabled: true
    current_version: "1.0.0"
    verification:
      algorithm: "sha256"
```

## Usage Examples

### Trigger OTA Update

```python
from world_engine.phase3.ota_manager import OTAManager, OTAUpdateType

ota = OTAManager(config)
update = ota.create_broadcast_update(
    version="1.1.0",
    alpha=0.015,  # Update thermal coefficient
    beta=0.25     # Update heat capacity
)
# Publish to MQTT topic: campus/+/+/ota/config
```

### Check Sync Status

```python
from world_engine.phase3.shadow_sync import ShadowSyncManager

sync = ShadowSyncManager(config)
report = sync.generate_sync_report()
print(f"Sync Rate: {report['sync_rate']}%")
print(f"Conflicts: {report['conflicts']}")
```

### Get Digital Twin Hierarchy

```python
from world_engine.phase3.digital_twin import DigitalTwinManager

dt = DigitalTwinManager(config)
hierarchy = dt.export_to_thingsboard_format()
print(f"Total Assets: {len(hierarchy['assets'])}")
```

## Dashboard Configuration

### Floor Plan Image Map

1. Upload floor plan image to ThingsBoard
2. Create Image Map Widget
3. Define polygons for each room using coordinates from metadata
4. Bind temperature telemetry to polygon color
5. Add JavaScript for color gradient:
   ```javascript
   function colorFromTemp(temp) {
       // Map 18°C-30°C to blue-red gradient
       const min = 18, max = 30;
       const ratio = (temp - min) / (max - min);
       const r = Math.round(255 * ratio);
       const b = Math.round(255 * (1 - ratio));
       return `rgb(${r}, 0, ${b})`;
   }
   ```

### Sync Status Table

Create a table widget with columns:
- Device Name
- Last Seen
- Desired HVAC
- Reported HVAC
- Desired Dimmer
- Reported Dimmer
- Sync Status

Filter to show only out-of-sync devices using the `sync_status` field.

### OTA Update Dashboard

Create cards showing:
- Total devices
- Updated count
- Pending updates
- Latest version
- Update success rate

## Security Considerations

### OTA Update Security

1. **SHA-256 Verification**: All updates must include a valid hash
2. **Sorted JSON Keys**: Ensures consistent hash calculation
3. **Tamper Alerts**: Failed verification triggers security alerts
4. **Audit Logging**: All update attempts are logged

### Network Security

- MQTT over TLS (port 8883) for production
- ThingsBoard authentication required
- Node-RED secured with user authentication
- Network isolation via Docker networks

## Troubleshooting

### ThingsBoard Connection Issues

```bash
# Check ThingsBoard logs
docker logs thingsboard

# Verify PostgreSQL is running
docker logs postgres-thingsboard

# Restart ThingsBoard
docker-compose -f docker-compose.phase3.yaml restart thingsboard
```

### Node-RED Flow Not Loading

```bash
# Check Node-RED logs
docker logs nodered

# Verify flow file exists
ls -la flows/phase3_gateway.json

# Restart Node-RED
docker-compose -f docker-compose.phase3.yaml restart nodered
```

### OTA Updates Not Applying

```bash
# Check World Engine logs
docker logs world-engine-phase3

# Verify MQTT connection
docker logs hivemq

# Test OTA topic subscription
mosquitto_sub -h localhost -t "campus/+/+/ota/config" -v
```

## API Reference

### Digital Twin Manager

```python
dt = DigitalTwinManager(config)
dt.get_asset(asset_id)
dt.get_assets_by_type(AssetType.ROOM)
dt.get_floor_rooms(floor_id)
dt.calculate_floor_aggregate(floor_id, telemetry_data)
```

### Shadow Sync Manager

```python
sync = ShadowSyncManager(config)
sync.update_desired_state(room_id, hvac_mode="on")
sync.update_reported_state(room_id, hvac_mode="on")
sync.get_out_of_sync_devices()
sync.generate_sync_report()
```

### OTA Manager

```python
ota = OTAManager(config)
ota.create_broadcast_update(version="1.1.0", alpha=0.015)
ota.create_targeted_update(target="B01", target_type=OTAUpdateType.TARGETED_BUILDING, version="1.1.0")
ota.verify_update(payload)
ota.get_update_statistics()
```

## Testing

### Unit Tests

```bash
pytest tests/test_phase3/
```

### Integration Tests

```bash
# Test OTA update flow
python tests/integration/test_ota_flow.py

# Test shadow synchronization
python tests/integration/test_shadow_sync.py

# Test digital twin provisioning
python tests/integration/test_digital_twin.py
```

## Migration from Phase 2

Phase 3 is fully backward compatible with Phase 2. To migrate:

1. Copy `config.phase2.yaml` to `config.phase3.yaml`
2. Add Phase 3 specific configuration sections
3. Update dependencies if needed
4. Run with Phase 3 engine:
   ```bash
   python -m world_engine.phase3.engine
   ```

## Performance Considerations

- **200 Devices**: Phase 3 handles 200 MQTT + 200 CoAP nodes
- **Memory Usage**: ~500MB for World Engine, ~1GB for ThingsBoard
- **CPU Usage**: Moderate, scales with device count
- **Network**: ~10 messages/second per device

## Future Enhancements

- CoAP integration for OTA updates
- Webhook support for external systems
- Machine learning for anomaly detection
- Mobile app for dashboard access
- Multi-campus support

## License

Same as Phase 1 & 2 - Academic project for SWAPD453 IoT Apps Development

## Contact

For issues or questions about Phase 3, refer to the project documentation or contact the course instructor.
