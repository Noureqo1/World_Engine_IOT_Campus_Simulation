# config.py
# ====================================================
# كل الإعدادات في مكان واحد — غيّر من هنا بس
# ====================================================

BROKER_HOST   = "localhost"
BROKER_PORT   = 1883

TB_URL        = "http://localhost:8080"
TB_USER       = "tenant@thingsboard.org"
TB_PASSWORD   = "tenant"

NUM_BUILDINGS = 2
NUM_FLOORS    = 10
NUM_ROOMS     = 20   # per floor  → total 400 rooms

# Physics defaults (يتغيروا بالـ OTA)
DEFAULT_ALPHA = 0.05   # thermal leakage
DEFAULT_BETA  = 0.80   # heat capacity
DEFAULT_TEMP  = 22.0   # starting temperature °C

TELEMETRY_INTERVAL = 5   # seconds
