#!/usr/bin/env python3
"""
Test MQTT connection to verify broker is working
"""
import paho.mqtt.client as mqtt
from config import BROKER_HOST, BROKER_PORT

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Successfully connected to MQTT broker")
        client.subscribe("test/topic")
        client.publish("test/topic", "Hello from test client")
    else:
        print(f"❌ Failed to connect, return code {rc}")

def on_message(client, userdata, msg):
    print(f"📨 Received message: {msg.topic} -> {msg.payload.decode()}")

def on_disconnect(client, userdata, rc):
    print("🔌 Disconnected from MQTT broker")

def main():
    print(f"🔍 Testing MQTT connection to {BROKER_HOST}:{BROKER_PORT}")
    
    client = mqtt.Client(client_id="test-client")
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    
    try:
        client.connect(BROKER_HOST, BROKER_PORT, 60)
        client.loop_start()
        
        # Wait for connection and test
        import time
        time.sleep(3)
        
        client.loop_stop()
        client.disconnect()
        print("✅ MQTT test completed successfully")
        
    except Exception as e:
        print(f"❌ MQTT test failed: {e}")

if __name__ == "__main__":
    main()
