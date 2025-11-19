# proximity_lock_system/utils.py
import bluetooth
from typing import List, Tuple

def discover_nearby_devices(duration: int = 5) -> List[Tuple[str, str]]:
    """
    Discover nearby Bluetooth devices.
    Returns a list of tuples: (mac, name)
    """
    try:
        devices = bluetooth.discover_devices(duration=duration, lookup_names=True)
        # On some platforms discover_devices(duration, lookup_names=True) returns list of tuples
        # On others, passing lookup_names=True may return list of tuples; ensure tuple form.
        normalized = []
        for item in devices:
            if isinstance(item, tuple) and len(item) >= 2:
                mac, name = item[0], item[1] or "Unknown"
            else:
                mac = item
                name = "Unknown"
            normalized.append((mac, name))
        return normalized
    except Exception as e:
        # If Bluetooth stack not available or error, return empty list
        return []
