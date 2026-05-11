# room_simulator.py
import json, time, random, threading
import paho.mqtt.client as mqtt
from config import *

class RoomSimulator:
    def __init__(self, building, floor, room):
        self.building = building          # e.g. "b01"
        self.floor    = floor             # e.g. "f01"
        self.room     = room             # e.g. "r001"
        self.room_id  = f"{building}-{floor}-{room}"

        # Physics state
        self.temperature      = DEFAULT_TEMP + random.uniform(-3, 3)
        self.alpha            = DEFAULT_ALPHA
        self.beta             = DEFAULT_BETA
        self.current_version  = "1.0"

        # Actuator state (reported)
        self.hvac_mode        = "OFF"
        self.lighting_dimmer  = 50

        # Desired state (comes from ThingsBoard shared attrs)
        self.desired_hvac     = "OFF"
        self.desired_dimmer   = 50

        # MQTT client — كل غرفة ليها client منفصل
        self.client = mqtt.Client(client_id=f"room-{self.room_id}")
        self.client.on_connect    = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message    = self._on_message
        
        # Add connection retry logic
        self.connected = False
        self.connect_mqtt()

    # ---- MQTT callbacks ----

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            print(f"[{self.room_id}] Connected to MQTT broker")
            # Subscribe لـ OTA (wildcard للـ floor والـ global)
            client.subscribe(f"campus/{self.building}/+/ota")
            # Subscribe لـ actuator commands
            client.subscribe(f"campus/cmd/{self.room_id}")
            # Subscribe لـ ThingsBoard shared attrs (لو بتشغل ThingsBoard MQTT API)
            client.subscribe(f"v1/devices/me/attributes")
        else:
            print(f"[{self.room_id}] Failed to connect, return code {rc}")
            self.connected = False

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        print(f"[{self.room_id}] Disconnected from MQTT broker")
        # Try to reconnect after 5 seconds
        threading.Timer(5.0, self.connect_mqtt).start()

    def connect_mqtt(self):
        """Connect to MQTT broker with retry logic"""
        try:
            print(f"[{self.room_id}] Connecting to MQTT broker at {BROKER_HOST}:{BROKER_PORT}...")
            self.client.connect(BROKER_HOST, BROKER_PORT, 60)
            self.client.loop_start()
        except Exception as e:
            print(f"[{self.room_id}] Connection failed: {e}")
            # Retry after 5 seconds
            threading.Timer(5.0, self.connect_mqtt).start()

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        try:
            data = json.loads(msg.payload.decode())
        except Exception:
            return

        if "/ota" in topic:
            self._handle_ota(data, topic)
        elif f"campus/cmd/{self.room_id}" in topic:
            self._handle_command(data)
        elif "attributes" in topic:
            self._handle_shared_attrs(data)

    # ---- OTA handler ----

    def _handle_ota(self, data, topic):
        import hashlib
        received_hash = data.pop("hash", None)
        if not received_hash:
            self._send_security_alert("NO_HASH", str(data))
            return

        canonical = json.dumps(data, sort_keys=True)
        computed  = hashlib.sha256(canonical.encode()).hexdigest()

        if computed != received_hash:
            self._send_security_alert("HASH_MISMATCH", canonical[:100])
            return

        # تحقق إن الـ update للـ floor الصح أو broadcast
        topic_parts = topic.split("/")
        target_floor = topic_parts[2]
        if target_floor != "+" and target_floor != self.floor:
            return   # مش ليّا

        # طبّق الـ params الجديدة
        if "alpha"   in data: self.alpha = data["alpha"]
        if "beta"    in data: self.beta  = data["beta"]
        if "version" in data:
            self.current_version = data["version"]
            # بلّغ ThingsBoard بالـ version الجديدة كـ client attribute
            self.client.publish(
                "v1/devices/me/attributes",
                json.dumps({"current_version": self.current_version})
            )
        print(f"[{self.room_id}] OTA applied: alpha={self.alpha}, beta={self.beta}, v={self.current_version}")

    # ---- Command handler (southbound) ----

    def _handle_command(self, data):
        method = data.get("method", "")
        params = data.get("params", {})

        if method == "setHvac":
            self.hvac_mode = params
            print(f"[{self.room_id}] HVAC set to {params}")
        elif method == "setDimmer":
            self.lighting_dimmer = int(params)
        elif method == "applyConfig":
            if "hvac_mode"       in params: self.hvac_mode       = params["hvac_mode"]
            if "lighting_dimmer" in params: self.lighting_dimmer = params["lighting_dimmer"]

        # أبلّغ ThingsBoard بالحالة الجديدة (reported state)
        self.client.publish("v1/devices/me/attributes", json.dumps({
            "client_hvac_mode":       self.hvac_mode,
            "client_lighting_dimmer": self.lighting_dimmer,
        }))

        # أبلّغ Node-RED بـ ACK (لإزالة "Pending" state)
        self.client.publish(
            f"campus/{self.building}/{self.floor}/ack/{self.room}",
            json.dumps({"ack": True, "method": method})
        )

    # ---- Shadow attrs handler ----

    def _handle_shared_attrs(self, data):
        if "shared_hvac_mode"       in data: self.desired_hvac   = data["shared_hvac_mode"]
        if "shared_lighting_dimmer" in data: self.desired_dimmer = data["shared_lighting_dimmer"]

    # ---- Security alert ----

    def _send_security_alert(self, alert_type, sample):
        self.client.publish("v1/devices/me/telemetry", json.dumps({
            "security_alert": {
                "type":    alert_type,
                "room_id": self.room_id,
                "sample":  sample[:150],
                "ts":      int(time.time() * 1000)
            }
        }))
        print(f"[SECURITY][{self.room_id}] {alert_type}")

    # ---- Physics loop ----

    def _update_physics(self):
        """معادلة الحرارة: dT = beta * hvac_effect - alpha * (T - T_ambient)"""
        T_ambient = 15.0
        hvac_effect = 5.0 if self.hvac_mode == "ON" else 0.0
        noise = random.gauss(0, 0.1)
        dT = self.beta * hvac_effect - self.alpha * (self.temperature - T_ambient) + noise
        self.temperature = round(self.temperature + dT, 2)
        self.temperature = max(10.0, min(40.0, self.temperature))

    def _publish_telemetry(self):
        """نشر التلمترى لـ ThingsBoard"""
        if not self.connected:
            print(f"[{self.room_id}] Not connected - skipping telemetry")
            return
            
        payload = {
            "temperature":    self.temperature,
            "hvac_mode":      self.hvac_mode,
            "lighting_dimmer": self.lighting_dimmer,
            "occupancy":      random.choice([0, 1, 1]),
            "co2_ppm":        random.randint(400, 1200),
            "current_version": self.current_version,
        }
        
        try:
            self.client.publish("v1/devices/me/telemetry", json.dumps(payload))
            # برضو نشر على topic الـ floor (عشان Node-RED يعمل aggregation)
            self.client.publish(
                f"campus/{self.building}/{self.floor}/{self.room}/telemetry",
                json.dumps(payload)
            )
        except Exception as e:
            print(f"[{self.room_id}] Failed to publish telemetry: {e}")

    def run(self):
        """الـ main loop"""
        while True:
            self._update_physics()
            self._publish_telemetry()
            time.sleep(TELEMETRY_INTERVAL)
