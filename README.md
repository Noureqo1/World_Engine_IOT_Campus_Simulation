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

## 🚀 Installation

### Prerequisites

- **Python 3.11+**
- **Docker & Docker Compose** (for containerized deployment)
- **Git**

### Option 1: Quick Start (Docker)

```bash
# Clone repository
git clone <repository-url>
cd IOT

# Start everything with Docker
make docker-up

# View logs
make docker-logs
```

### Option 2: Local Development

```bash
# Complete first-time setup
make quickstart

# Or manual steps:
make setup              # Create venv
source venv/Scripts/activate  # Activate venv
make install            # Install dependencies
make init-db            # Initialize database

# Run in mock mode (no MQTT broker needed)
make run-mock

# Or with MQTT broker
make run
```

---

## 📖 Usage

### Running the Simulation

#### Local (Mock Mode - No MQTT)
```bash
# Fastest way to test
python main.py --mock
```

#### Local (With Mosquitto)
```bash
# Requires Mosquitto running on localhost:1883
python main.py
```

#### Docker Compose
```bash
# Start all services
make docker-up

# Monitor logs
make docker-logs

# Stop services
make docker-down
```

### Subscribing to MQTT Topics

```bash
# All campus telemetry
make subscribe

# Specific room
make subscribe-room ROOM=101

# Fleet health
make health

# Performance metrics
make metrics
```

### Database Operations

```bash
# Show database statistics
make db-status

# Backup database
make db-backup

# Run custom query
make db-query SQL="SELECT * FROM room_states WHERE last_temp > 25"

# Reset database
make db-reset
```

---

## ⚙️ Configuration

### config.yaml

```yaml
simulation:
  tick_interval: 5.0              # seconds between updates
  startup_jitter_max: 5.0         # random startup delay (0-5s)
  time_acceleration: 60           # 60x speed (1 min = 1 hour)

  night_cycle:
    enabled: true
    base_temp: 15.0               # average outside temp
    amplitude: 8.0                # ±8°C variation
    coldest_hour: 4               # 4 AM coldest

building:
  id: "b01"
  floors: 10
  rooms_per_floor: 20

mqtt:
  broker_host: "localhost"        # Use "mosquitto" in Docker
  broker_port: 1883
  client_id_prefix: "world_engine"

database:
  path: "world_engine.db"
  batch_interval: 30              # seconds between commits

faults:
  enabled: true
  sensor_drift_probability: 0.02  # 2% per tick
  frozen_sensor_probability: 0.01
  telemetry_delay_probability: 0.03
  node_dropout_probability: 0.005

health:
  heartbeat_timeout: 60           # seconds
  check_interval: 10
  publish_interval: 30

metrics:
  enabled: true
  publish_interval: 30
```

### Environment Variables (Docker)

```bash
MQTT_HOST=mosquitto
MQTT_PORT=1883
DB_PATH=/app/data/world_engine.db
```

---

## 🧪 Testing

### Manual Testing

```bash
# Test MQTT connectivity
make test-mqtt

# View sample sensor readings
make test-sensors

# Validate project structure
make validate
```

### Interactive Testing

1. **Start simulation**:
   ```bash
   make docker-up
   ```

2. **Open another terminal and subscribe**:
   ```bash
   make subscribe
   ```

3. **Observe**:
   - Room telemetry (temperature, humidity, occupancy)
   - Fault injection (`"faults": ["sensor_drift"]`)
   - Night cycle (outside temp changing)

4. **Test state restoration**:
   ```bash
   make docker-restart
   # Check logs - should see "Restored state for 200 rooms"
   ```

### Wokwi ESP32 POC

1. Go to https://wokwi.com/projects/new/micropython-esp32
2. Copy `wokwi/main.py` into code editor
3. Copy `wokwi/diagram.json` into diagram tab
4. Click **Start Simulation**
5. Observe Serial Monitor output

---

## 📁 Project Structure

```
d:/IOT/
├── main.py                          # Entry point
├── config.yaml                      # Configuration
├── requirements.txt                 # Python dependencies
├── Makefile                         # Command shortcuts
├── README.md                        # This file
├── Dockerfile                       # Container image
├── docker-compose.yaml              # Multi-container setup
│
├── world_engine/                    # Main package
│   ├── __init__.py
│   ├── core/                        # Core logic
│   │   ├── models.py                # Room class + physics
│   │   ├── faults.py                # Fault injection
│   │   └── health.py                # Fleet health monitor
│   ├── db/                          # Database layer
│   │   └── db_setup.py              # SQLite async operations
│   ├── mqtt/                        # MQTT client
│   │   └── publisher.py             # Async MQTT with retry
│   └── utils/                       # Utilities
│       ├── config.py                # Config loader
│       └── metrics.py               # Performance tracking
│
├── wokwi/                           # Hardware POC
│   ├── main.py                      # MicroPython code
│   ├── diagram.json                 # Circuit wiring
│   └── wokwi.toml                   # Project config
│
└── docker/                          # Docker configs
    └── mosquitto/config/
        └── mosquitto.conf           # MQTT broker config
```

---

## 🔧 Troubleshooting

### Issue: MQTT Connection Refused

**Symptom**: `MqttError: [Errno 111] Connection refused`

**Solution**:
```bash
# Check if Mosquitto is running
make mosquitto-status

# Restart containers
make docker-restart

# Or use mock mode
make run-mock
```

### Issue: Database Locked

**Symptom**: `sqlite3.OperationalError: database is locked`

**Solution**:
```bash
# Increase batch interval in config.yaml
database:
  batch_interval: 60  # Increase from 30 to 60

# Or restart simulation
make docker-restart
```

### Issue: High CPU Usage

**Symptom**: CPU > 50%

**Solution**:
```bash
# Increase tick interval
simulation:
  tick_interval: 10.0  # Increase from 5 to 10 seconds

# Reduce room count
building:
  floors: 5            # Reduce from 10 to 5
  rooms_per_floor: 10  # Reduce from 20 to 10
```

### Issue: Wokwi Serial Monitor Empty

**Solution**:
1. Check pin assignments match `diagram.json`
2. Refresh page (F5)
3. Use simplified test code (see README section on Wokwi)

---

## 🤝 Contributing

### Coding Standards

- **Python**: PEP 8, type hints, docstrings
- **Async**: Use `asyncio`, avoid blocking calls
- **Logging**: Use `logging` module, not `print()`
- **Config**: Externalize in `config.yaml`

### Pull Request Process

1. Fork repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

---

## 📄 License

This project is licensed under the MIT License.

---

## 👤 Author

**Nour Eldin** - Student ID: 202201310
**Course**: SWAPD453 - IoT Application Development
**Institution**: [Your University]

---

## 🙏 Acknowledgments

- **Eclipse Mosquitto** - MQTT broker
- **Python asyncio** - Async framework
- **aiosqlite** - Async SQLite
- **aiomqtt** - Async MQTT client
- **Wokwi** - ESP32 simulation platform

---

## 📖 Documentation

### Project Documentation

- **[README.md](README.md)** - Complete project overview (this file)
- **[QUICKSTART.md](QUICKSTART.md)** - 5-minute getting started guide
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Contribution guidelines

### POC Submission Materials

- **[POC Report](docs/POC_REPORT.md)** - Comprehensive 13-page technical report
- **[Video Guide](docs/VIDEO_GUIDE.md)** - Step-by-step video recording instructions (2-3 min demo)
- **[Screenshot Guide](docs/SCREENSHOT_GUIDE.md)** - Instructions for capturing 6 required screenshots
- **[Submission Checklist](docs/SUBMISSION_CHECKLIST.md)** - Complete pre-submission review checklist

### TA Discussion Preparation

**🎯 Start here**: [TA Preparation Master Guide](docs/TA_PREPARATION_MASTER.md)

Comprehensive preparation materials for your TA discussion (4 documents):

1. **[TA Discussion Q&A](docs/TA_DISCUSSION_QA.md)** - 60+ questions with detailed technical answers
   - Use for: Comprehensive study 3-4 days before meeting
   - Covers: Architecture, implementation, faults, POC, Docker, performance, future work
   - Format: 10 sections with in-depth explanations and code examples

2. **[TA Cheat Sheet](docs/TA_CHEAT_SHEET.md)** - Quick reference guide with key facts
   - Use for: During the actual discussion (print or second screen)
   - Contains: Key numbers, formulas, command reference, gotcha questions
   - Format: Condensed tables and one-liners for instant recall

3. **[TA Practice Script](docs/TA_PRACTICE_SCRIPT.md)** - Rehearsal scripts to practice out loud
   - Use for: 1-2 days before meeting to rehearse answers
   - Contains: 10 practice sessions with natural conversational answers
   - Format: Question → Answer → Practice tips

4. **[TA Presentation Outline](docs/TA_PRESENTATION_OUTLINE.md)** - Formal 5-minute presentation structure
   - Use for: If TA requests structured walkthrough
   - Contains: 8-slide presentation flow, live demo steps, timing guide
   - Format: Slide-by-slide script with visuals and talking points

**Preparation Timeline**: Follow [TA_PREPARATION_MASTER.md](docs/TA_PREPARATION_MASTER.md) for 3-4 day study plan.

---

## 📚 References

- [Phase 1 Specification](docs/SWAPD453_IoT_App_Dev_Project.pdf)
- [MQTT Documentation](https://mqtt.org/)
- [MicroPython Docs](https://docs.micropython.org/)
- [Docker Docs](https://docs.docker.com/)

---

**Made with ❤️ for IoT education**
