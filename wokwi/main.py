import machine
import time
import json
import network
import dht
from umqtt.simple import MQTTClient

# WiFi & MQTT settings
WIFI_SSID = "Wokwi-GUEST"
WIFI_PASSWORD = ""
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_CLIENT_ID = "esp32_room_poc"

# Room info
BUILDING = "b01"
FLOOR = 1
ROOM_NUMBER = 101

# Pin assignments (MATCH YOUR DIAGRAM!)
DHT_PIN = 15   # Changed from 4
PIR_PIN = 14   # Changed from 5
LDR_PIN = 34   # Correct

PUBLISH_INTERVAL = 5

# Initialize sensors
dht_sensor = dht.DHT22(machine.Pin(DHT_PIN))
pir_sensor = machine.Pin(PIR_PIN, machine.Pin.IN)
ldr_adc = machine.ADC(machine.Pin(LDR_PIN))
ldr_adc.atten(machine.ADC.ATTN_11DB)

hvac_mode = "off"
lighting_dimmer = 50

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if not wlan.isconnected():
        print("Connecting to WiFi:", WIFI_SSID)
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        
        timeout = 10
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
            print(".")
    
    if wlan.isconnected():
        print("Connected! IP:", wlan.ifconfig()[0])
        return True
    else:
        print("WiFi connection failed!")
        return False

def read_sensors():
    try:
        dht_sensor.measure()
        temperature = dht_sensor.temperature()
        humidity = dht_sensor.humidity()
    except:
        temperature = 25.0
        humidity = 50.0
    
    occupancy = bool(pir_sensor.value())
    raw_light = ldr_adc.read()
    light_level = int((raw_light / 4095) * 1000)
    
    return {
        "temperature": round(temperature, 2),
        "humidity": round(humidity, 2),
        "occupancy": occupancy,
        "light_level": light_level
    }

def build_payload(sensor_data):
    room_id = "{}-f{:02d}-r{:03d}".format(BUILDING, FLOOR, ROOM_NUMBER)
    
    payload = {
        "metadata": {
            "sensor_id": room_id,
            "building": BUILDING,
            "floor": FLOOR,
            "room": ROOM_NUMBER,
            "timestamp": int(time.time())
        },
        "sensors": sensor_data,
        "actuators": {
            "hvac_mode": hvac_mode,
            "lighting_dimmer": lighting_dimmer
        }
    }
    return payload

def get_mqtt_topic():
    return "campus/{}/floor_{:02d}/room_{:03d}/telemetry".format(BUILDING, FLOOR, ROOM_NUMBER)

# Main program
print("=" * 50)
print("ESP32 IoT Sensor Node - World Engine POC")
print("=" * 50)

if not connect_wifi():
    print("Cannot proceed without WiFi")
else:
    print("Connecting to MQTT:", MQTT_BROKER)
    try:
        mqtt = MQTTClient(MQTT_CLIENT_ID, MQTT_BROKER, port=MQTT_PORT)
        mqtt.connect()
        print("MQTT connected!")
    except Exception as e:
        print("MQTT failed:", e)
        mqtt = None
    
    topic = get_mqtt_topic()
    print("Publishing to:", topic)
    print("-" * 50)
    
    while True:
        try:
            sensor_data = read_sensors()
            payload = build_payload(sensor_data)
            payload_json = json.dumps(payload)
            
            if mqtt:
                mqtt.publish(topic, payload_json)
            
            # Print in one line (no multi-line f-strings)
            print("T={}C H={}% Occ={} Light={}".format(
                sensor_data['temperature'],
                sensor_data['humidity'],
                sensor_data['occupancy'],
                sensor_data['light_level']
            ))
        except Exception as e:
            print("Error:", e)
        
        time.sleep(PUBLISH_INTERVAL)