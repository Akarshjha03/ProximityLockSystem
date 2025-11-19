# proximity_lock_system/config.py
import json
import os

CONFIG_PATH = os.path.expanduser("~/.proximity_lock_config.json")

DEFAULTS = {
    "PHONE_MAC": None,
    "DEVICE_NAME": None,
    "POLL_INTERVAL": 10,
    "UNLOCK_PAUSE": 180,
    "SAFETY_THRESHOLD": 2,
    "SCAN_DURATION": 5
}

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            # merge defaults
            for k, v in DEFAULTS.items():
                data.setdefault(k, v)
            return data
        except Exception:
            return DEFAULTS.copy()
    else:
        return DEFAULTS.copy()

def save_config(cfg: dict):
    merged = DEFAULTS.copy()
    merged.update(cfg or {})
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=4)

def reset_config():
    if os.path.exists(CONFIG_PATH):
        os.remove(CONFIG_PATH)
