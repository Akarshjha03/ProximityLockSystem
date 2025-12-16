# proximity_lock_system/core.py
import platform
import subprocess
import time
import threading
from typing import Optional

from .utils import discover_nearby_devices
from .config import load_config

# Helper: lock the system safely (no unlock)
def lock_system():
    os_name = platform.system()
    try:
        if os_name == "Windows":
            # Lock workstation
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=False, shell=True)
        elif os_name == "Darwin":  # macOS
            subprocess.run('/System/Library/CoreServices/Menu\\ Extras/User.menu/Contents/Resources/CGSession -suspend', shell=True, check=False)
        elif os_name == "Linux":
            # Try common locker commands - GNOME, KDE, XDG screensaver
            subprocess.run("gnome-screensaver-command -l", shell=True, check=False)
            subprocess.run("xdg-screensaver lock", shell=True, check=False)
        # print handled by caller
    except Exception:
        pass

def is_device_in_range(target_mac: str, duration: int = 4) -> bool:
    """
    Returns True if `target_mac` is found in nearby bluetooth scans.
    Uses discover_nearby_devices() which returns list of (mac, name).
    """
    try:
        found = discover_nearby_devices(duration=duration)
        for mac, _ in found:
            if mac and mac.lower() == target_mac.lower():
                return True
        return False
    except Exception:
        return False

class MonitorThread(threading.Thread):
    """
    Background monitor thread that checks device presence and locks system.
    Controlled with start() and stop() via CLI.
    """
    def __init__(self, phone_mac: str, poll_interval: int, pause_after_unlock: int, safety_threshold: int, scan_duration: int):
        super().__init__(daemon=True)
        self.phone_mac = phone_mac
        self.poll_interval = max(1, int(poll_interval))
        self.pause_after_unlock = max(0, int(pause_after_unlock))
        self.safety_threshold = max(1, int(safety_threshold))
        self.scan_duration = max(1, int(scan_duration))
        self._stop_evt = threading.Event()
        self._paused_until = 0
        self._running = False
        self.last_seen = 0  # Timestamp of last successful detection

    def stop(self):
        self._stop_evt.set()

    def stopped(self):
        return self._stop_evt.is_set()

    def run(self):
        self._running = True
        consecutive_misses = 0
        # Main loop
        while not self.stopped():
            # If paused due to recent lock/unlock, skip checks
            if time.time() < self._paused_until:
                time.sleep(self.poll_interval)
                continue

            try:
                in_range = is_device_in_range(self.phone_mac, duration=self.scan_duration)
            except Exception:
                in_range = False

            if not in_range:
                consecutive_misses += 1
                print(f"\033[33m[!] Device not detected ({consecutive_misses}/{self.safety_threshold})\033[0m")
                if consecutive_misses >= self.safety_threshold:
                    print("\033[31m[!] Device absent for threshold — locking system now.\033[0m")
                    lock_system()
                    # Pause checks for configured duration after lock (user must manually unlock)
                    self._paused_until = time.time() + self.pause_after_unlock
                    consecutive_misses = 0
            else:
                self.last_seen = time.time()
                # reset counter
                if consecutive_misses > 0:
                    print("\033[32m[+] Device detected again — resetting counter.\033[0m")
                consecutive_misses = 0
                # keep monitoring
            # Wait poll interval (but check stop event frequently)
            for _ in range(max(1, int(self.poll_interval))):
                if self.stopped():
                    break
                time.sleep(1)
        self._running = False

