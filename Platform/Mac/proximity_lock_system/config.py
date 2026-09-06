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
    "SCAN_DURATION": 5,
}

def load_config() -> dict:
    """Load configuration from disk, merging with defaults."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in DEFAULTS.items():
                data.setdefault(k, v)
            return data
        except Exception:
            return DEFAULTS.copy()
    return DEFAULTS.copy()

def save_config(cfg: dict):
    """Persist configuration to disk."""
    merged = DEFAULTS.copy()
    merged.update(cfg or {})
    # CONFIG_PATH is directly in ~/ so no sub-dir to create, but guard anyway
    parent = os.path.dirname(CONFIG_PATH)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=4)

def reset_config():
    """Delete the configuration file."""
    if os.path.exists(CONFIG_PATH):
        os.remove(CONFIG_PATH)
