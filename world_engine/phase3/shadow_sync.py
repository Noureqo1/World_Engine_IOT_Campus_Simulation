# shadow_sync.py
# يعمل كـ daemon منفصل — يفحص كل الأجهزة ويبعت تحديثات
import json, time, requests
from config import TB_URL, TB_USER, TB_PASSWORD

def get_token():
    r = requests.post(f"{TB_URL}/api/auth/login",
        json={"username": TB_USER, "password": TB_PASSWORD})
    return r.json()["token"]

def get_all_devices(token):
    headers = {"X-Authorization": f"Bearer {token}"}
    r = requests.get(f"{TB_URL}/api/tenant/devices?pageSize=500&page=0", headers=headers)
    return r.json().get("data", [])

def get_device_attrs(token, device_id):
    headers = {"X-Authorization": f"Bearer {token}"}
    # Shared (desired)
    shared = requests.get(
        f"{TB_URL}/api/plugins/telemetry/DEVICE/{device_id}/values/attributes/SHARED_SCOPE",
        headers=headers).json()
    # Client (reported)
    client = requests.get(
        f"{TB_URL}/api/plugins/telemetry/DEVICE/{device_id}/values/attributes/CLIENT_SCOPE",
        headers=headers).json()
    return shared, client

def check_sync_status(token):
    """يرجع list بالأجهزة اللي out-of-sync"""
    devices = get_all_devices(token)
    out_of_sync = []

    for device in devices:
        dev_id = device["id"]["id"]
        shared_attrs, client_attrs = get_device_attrs(token, dev_id)

        shared_dict = {a["key"]: a["value"] for a in shared_attrs}
        client_dict = {a["key"]: a["value"] for a in client_attrs}

        desired_hvac   = shared_dict.get("shared_hvac_mode")
        reported_hvac  = client_dict.get("client_hvac_mode")
        desired_dimmer = shared_dict.get("shared_lighting_dimmer")
        reported_dimmer= client_dict.get("client_lighting_dimmer")
        desired_ver    = shared_dict.get("current_version")
        reported_ver   = client_dict.get("current_version")

        hvac_mismatch   = desired_hvac   and desired_hvac   != reported_hvac
        dimmer_mismatch = desired_dimmer and desired_dimmer != reported_dimmer
        ver_mismatch    = desired_ver    and desired_ver    != reported_ver

        if hvac_mismatch or dimmer_mismatch or ver_mismatch:
            out_of_sync.append({
                "device_name":      device["name"],
                "device_id":        dev_id,
                "desired_hvac":     desired_hvac,
                "reported_hvac":    reported_hvac,
                "desired_dimmer":   desired_dimmer,
                "reported_dimmer":  reported_dimmer,
                "desired_version":  desired_ver,
                "reported_version": reported_ver,
            })

    return out_of_sync

def run_shadow_monitor():
    """يشغل مراقبة دورية كل 30 ثانية"""
    token = get_token()
    while True:
        out_of_sync = check_sync_status(token)
        if out_of_sync:
            print(f"\n[SHADOW] {len(out_of_sync)} devices out of sync:")
            for d in out_of_sync:
                print(f"  {d['device_name']}: HVAC {d['desired_hvac']}≠{d['reported_hvac']}"
                      f" | Dimmer {d['desired_dimmer']}≠{d['reported_dimmer']}"
                      f" | Ver {d['desired_version']}≠{d['reported_version']}")
        else:
            print("[SHADOW] All devices in sync.")
        time.sleep(30)

if __name__ == "__main__":
    run_shadow_monitor()
