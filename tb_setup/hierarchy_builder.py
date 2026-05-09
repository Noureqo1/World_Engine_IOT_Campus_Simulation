# hierarchy_builder.py
import requests, json, random, time
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import TB_URL, TB_USER, TB_PASSWORD, NUM_BUILDINGS, NUM_FLOORS, NUM_ROOMS

ROOM_TYPES = ["lecture_hall", "lab", "office", "corridor"]

def login():
    r = requests.post(f"{TB_URL}/api/auth/login",
        json={"username": TB_USER, "password": TB_PASSWORD})
    return r.json()["token"]

def headers(token):
    return {"X-Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def create_asset(token, name, asset_type):
    r = requests.post(f"{TB_URL}/api/asset",
        headers=headers(token),
        json={"name": name, "type": asset_type})
    data = r.json()
    if "id" not in data:
        print(f"[ERROR] Failed to create {name}: {data}")
        return None
    print(f"[OK] Created asset: {name}")
    return data["id"]["id"]

def add_relation(token, from_id, to_id, from_type="ASSET", to_type="ASSET"):
    requests.post(f"{TB_URL}/api/relation",
        headers=headers(token),
        json={
            "from": {"id": from_id, "entityType": from_type},
            "to":   {"id": to_id,   "entityType": to_type},
            "type": "Contains",
            "typeGroup": "COMMON"
        })

def set_server_attrs(token, asset_id, attrs):
    requests.post(
        f"{TB_URL}/api/plugins/telemetry/ASSET/{asset_id}/attributes/SERVER_SCOPE",
        headers=headers(token),
        json=attrs
    )

def build():
    token = login()
    print(f"[AUTH] Token acquired")

    # Campus root
    campus_id = create_asset(token, "ZC-Main-Campus", "campus")

    for b in range(1, NUM_BUILDINGS + 1):
        bld_name = f"B{b:02d}"
        bld_id   = create_asset(token, bld_name, "building")
        add_relation(token, campus_id, bld_id)

        for f in range(1, NUM_FLOORS + 1):
            flr_name = f"B{b:02d}-F{f:02d}"
            flr_id   = create_asset(token, flr_name, "floor")
            add_relation(token, bld_id, flr_id)

            for r in range(1, NUM_ROOMS + 1):
                room_name = f"B{b:02d}-F{f:02d}-R{r:03d}"
                room_id   = create_asset(token, room_name, "room")
                add_relation(token, flr_id, room_id)

                # Server-side static metadata
                set_server_attrs(token, room_id, {
                    "square_footage":    random.randint(25, 120),
                    "occupant_capacity": random.randint(10, 60),
                    "coordinates_x":     random.randint(50, 700),
                    "coordinates_y":     random.randint(50, 500),
                    "room_type":         random.choice(ROOM_TYPES),
                    "current_version":   "1.0"
                })

                time.sleep(0.05)  # عشان ما نـ overload الـ API

    print(f"\n[DONE] Hierarchy built successfully!")

if __name__ == "__main__":
    build()
