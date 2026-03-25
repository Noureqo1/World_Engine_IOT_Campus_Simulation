# World Engine - IoT Campus Simulation

## 🎯 Overview

**World Engine** is a scalable IoT simulation platform that models a smart campus with 200 sensor-equipped rooms across 10 floors. Each room features:

- **Environmental sensors**: Temperature, humidity, light level, occupancy
- **Actuators**: HVAC system, lighting dimmer
- **Thermal physics**: First-order heat transfer model
- **Fault injection**: Realistic sensor failures and network issues
- **Real-time telemetry**: MQTT-based pub/sub architecture
- **State persistence**: SQLite database with async operations

### Key Stats

- **200 concurrent rooms** running in asyncio event loop
- **~40 messages/sec** telemetry throughput
- **<0.1ms** event loop latency (Python asyncio)
- **<40MB** memory footprint
- **Fault types**: Sensor drift, frozen sensors, telemetry delays, node dropouts

---

## ✨ Features

### Phase 1 (Current)

#### Core Simulation
- ✅ **200 concurrent rooms** with unique IDs (`b01-f05-r502`)
- ✅ **Thermal physics simulation** using differential heat transfer
- ✅ **Night cycle** with sinusoidal temperature variation
- ✅ **Environmental correlations** (occupancy → light levels)
- ✅ **HVAC auto-control** (off/eco/on modes)

#### Fault Injection
- ✅ **Sensor drift**: Gradual bias accumulation (±5°C max)
- ✅ **Frozen sensors**: Stuck at last known value
- ✅ **Telemetry delays**: 0.5-3 second MQTT publish delays
- ✅ **Node dropouts**: Complete node failure for 15-100 seconds

#### Monitoring & Observability
- ✅ **Fleet health**: 60-second heartbeat timeout detection
- ✅ **Performance metrics**: CPU, memory, event loop latency
- ✅ **State persistence**: SQLite with batched commits (30s intervals)
- ✅ **State restoration**: Resume from last known state on restart
- ✅ **Data validation**: Sensor range checking and clamping

#### Deployment
- ✅ **Docker containerization** with multi-stage builds
- ✅ **Docker Compose** orchestration (Mosquitto + World Engine)
- ✅ **Environment variable** configuration
- ✅ **Health checks** for containers

#### Hardware POC
- ✅ **Wokwi ESP32 simulation** with MicroPython
- ✅ **DHT22, PIR, LDR** sensor integration
- ✅ **WiFi + MQTT** connectivity
- ✅ **Matching JSON schema** with simulation

---

## 🏗️ Architecture

### System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     World Engine                            │
│                                                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │  Room 001  │  │  Room 002  │  │  Room 200  │           │
│  │  Physics   │  │  Physics   │  │  Physics   │  ... x200  │
│  │  Faults    │  │  Faults    │  │  Faults    │           │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘           │
│        │                │                │                   │
│        └────────────────┴────────────────┘                   │
│                         │                                    │
│               ┌─────────▼─────────┐                          │
│               │  MQTT Publisher   │                          │
│               └─────────┬─────────┘                          │
│                         │                                    │
│        ┌────────────────┼────────────────┐                  │
│        │                │                │                   │
│   ┌────▼────┐   ┌──────▼──────┐   ┌────▼────┐             │
│   │  Health │   │  Metrics    │   │  SQLite │             │
│   │ Monitor │   │  Tracker    │   │   DB    │             │
│   └─────────┘   └─────────────┘   └─────────┘             │
└─────────────────────────┬───────────────────────────────────┘
                          │
                ┌─────────▼─────────┐
                │   Mosquitto MQTT  │
                │      Broker       │
                └───────────────────┘
                          │
                ┌─────────▼─────────┐
                │   External        │
                │   Subscribers     │
                │   (Analytics,     │
                │    Dashboards)    │
                └───────────────────┘
```

### Data Flow

1. **Room Loop** (every 5 seconds):
   - Update physics (temperature, humidity)
   - Apply fault conditions (if active)
   - Validate sensor readings
   - Build JSON payload
   - Publish to MQTT topic

2. **Background Tasks**:
   - **Health Monitor**: Check heartbeats every 10s, report every 30s
   - **Metrics Tracker**: Measure CPU/memory/latency, report every 30s
   - **DB Committer**: Batch commit room states every 30s

---



## 📚 References

- [Phase 1 Specification](docs/SWAPD453_IoT_App_Dev_Project.pdf)
- [MQTT Documentation](https://mqtt.org/)
- [MicroPython Docs](https://docs.micropython.org/)
- [Docker Docs](https://docs.docker.com/)

---
