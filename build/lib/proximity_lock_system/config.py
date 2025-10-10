import json
import os

CONFIG_FILE = os.path.expanduser("~/.proximity_lock_config.json")

def load_config():
    """Load configuration from local JSON file."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return None

def save_config(data):
    """Save user configuration to JSON."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)

def delete_config():
    """Reset configuration if needed."""
    if os.path.exists(CONFIG_FILE):
        os.remove(CONFIG_FILE)
