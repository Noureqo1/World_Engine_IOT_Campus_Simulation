# ota_handler.py
# يُستخدم كـ utility مستقل أو يُستورد في room_simulator
import json, hashlib

def verify_and_extract(raw_payload: str) -> tuple[dict | None, str | None]:
    """
    يتحقق من الـ SHA-256 hash ويرجع (data, None) لو صح
    أو (None, error_message) لو في مشكلة
    """
    try:
        data = json.loads(raw_payload)
    except json.JSONDecodeError:
        return None, "MALFORMED_JSON"

    received_hash = data.pop("hash", None)
    if not received_hash:
        return None, "NO_HASH"

    # المفتاح: sort_keys=True لازم يتطابق مع الـ publisher
    canonical = json.dumps(data, sort_keys=True)
    computed  = hashlib.sha256(canonical.encode()).hexdigest()

    if computed != received_hash:
        return None, f"HASH_MISMATCH: got={received_hash[:16]}... expected={computed[:16]}..."

    return data, None


def build_signed_payload(params: dict) -> str:
    """
    يبني الـ payload مع الـ hash (يُستخدم في الـ publisher)
    """
    canonical = json.dumps(params, sort_keys=True)
    params["hash"] = hashlib.sha256(canonical.encode()).hexdigest()
    return json.dumps(params)
