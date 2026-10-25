# proximity_lock_system/utils.py
from typing import List, Tuple

try:
    import bluetooth
except ImportError as import_error:
    bluetooth = None
    _BLUETOOTH_IMPORT_ERROR = import_error
else:
    _BLUETOOTH_IMPORT_ERROR = None


class BluetoothScanError(RuntimeError):
    """Raised when a scan could not determine whether the device is nearby."""

def discover_nearby_devices(duration: int = 5) -> List[Tuple[str, str]]:
    """
    Discover nearby Bluetooth devices.
    Returns a list of tuples: (mac, name)
    """
    if bluetooth is None:
        raise BluetoothScanError(f"Bluetooth dependency is unavailable: {_BLUETOOTH_IMPORT_ERROR}")
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
    except Exception as exc:
        # Scanner failure is not evidence that the phone is out of range.
        raise BluetoothScanError(str(exc)) from exc
