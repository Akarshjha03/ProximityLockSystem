# proximity_lock_system/utils.py
"""
Bluetooth discovery for macOS using bleak (BLE via CoreBluetooth).

Why bleak instead of pybluez?
- pybluez relies on IOBluetooth classic discovery which requires root on
  modern macOS (12+) and is effectively unmaintained.
- bleak wraps Apple's CoreBluetooth framework natively and works in user-space.
- Most modern iOS/Android phones broadcast BLE advertisements even with classic
  discovery disabled, making BLE a more reliable proximity signal.

Note on MAC address availability:
  CoreBluetooth intentionally randomises or hides the real hardware MAC address
  for privacy.  bleak exposes a UUID-based identifier on macOS instead of a
  true 48-bit MAC.  Therefore:
    - On first run users *scan* and pick their phone from a list.
    - We store the CoreBluetooth UUID (looks like a UUID4) as "PHONE_MAC".
    - Subsequent scans match against that stored UUID.
"""

import asyncio
from typing import List, Tuple

try:
    from bleak import BleakScanner
    _BLEAK_AVAILABLE = True
except ImportError:
    _BLEAK_AVAILABLE = False


async def _async_scan(duration: float) -> List[Tuple[str, str]]:
    """Async BLE scan; returns list of (identifier, name)."""
    devices = await BleakScanner.discover(timeout=duration)
    results: List[Tuple[str, str]] = []
    for d in devices:
        identifier = str(d.address)          # UUID on macOS
        name = d.name or "Unknown"
        results.append((identifier, name))
    return results


def discover_nearby_devices(duration: int = 5) -> List[Tuple[str, str]]:
    """
    Discover nearby BLE devices.
    Returns a list of tuples: (identifier, name)

    On macOS the 'identifier' is a CoreBluetooth UUID, not a classic MAC.
    """
    if not _BLEAK_AVAILABLE:
        print("\033[31m[!] bleak is not installed. Run: pip install bleak\033[0m")
        return []
    try:
        return asyncio.run(_async_scan(float(duration)))
    except Exception as e:
        # Surface the error so the user knows if Bluetooth is off, etc.
        print(f"\033[33m[!] BLE scan error: {e}\033[0m")
        return []
