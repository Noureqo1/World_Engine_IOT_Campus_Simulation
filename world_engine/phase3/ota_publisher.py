# ota_publisher.py
import json, hashlib, argparse
import paho.mqtt.client as mqtt
from config import BROKER_HOST, BROKER_PORT

def sign_payload(params: dict) -> dict:
    """يضيف SHA-256 hash للـ payload"""
    canonical    = json.dumps(params, sort_keys=True)
    params["hash"] = hashlib.sha256(canonical.encode()).hexdigest()
    return params

def publish_ota(building="b01", floor="+", params=None, version="1.1"):
    """
    floor="+"  → broadcast لكل الـ floors في الـ building
    floor="f05" → فقط Floor 5
    """
    if params is None:
        params = {}

    payload = {
        "alpha":   params.get("alpha",   0.05),
        "beta":    params.get("beta",    0.80),
        "version": version,
    }
    signed = sign_payload(payload)

    topic = f"campus/{building}/{floor}/ota"

    client = mqtt.Client(client_id="ota-publisher")
    client.connect(BROKER_HOST, BROKER_PORT)
    client.publish(topic, json.dumps(signed), qos=1)
    client.disconnect()

    print(f"[OTA] Published v{version} → {topic}")
    print(f"      Params: alpha={payload['alpha']}, beta={payload['beta']}")
    print(f"      Hash:   {signed['hash'][:32]}...")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--building", default="b01")
    parser.add_argument("--floor",    default="+", help="'+' for all floors")
    parser.add_argument("--alpha",    type=float, default=0.07)
    parser.add_argument("--beta",     type=float, default=0.75)
    parser.add_argument("--version",  default="1.1")
    args = parser.parse_args()

    publish_ota(
        building=args.building,
        floor=args.floor,
        params={"alpha": args.alpha, "beta": args.beta},
        version=args.version,
    )

# مثال تشغيل:
# python ota_publisher.py --floor + --version 1.1 --alpha 0.07 --beta 0.75
# python ota_publisher.py --floor f05 --version 1.1 --alpha 0.06
