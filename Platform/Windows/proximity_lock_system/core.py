# proximity_lock_system/core.py
import platform
import subprocess
import time
import threading
from typing import Optional

from .utils import BluetoothScanError, discover_nearby_devices

# Helper: lock the system safely (no unlock)
def lock_system():
    os_name = platform.system()
    try:
        if os_name == "Windows":
            # Lock workstation
            result = subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=False, timeout=10)
        elif os_name == "Darwin":  # macOS
            result = subprocess.run(["/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession", "-suspend"], check=False, timeout=10)
        elif os_name == "Linux":
            # Try common locker commands - GNOME, KDE, XDG screensaver
            for command in ("gnome-screensaver-command -l", "xdg-screensaver lock"):
                result = subprocess.run(command, shell=True, check=False, timeout=10)
                if result.returncode == 0:
                    return True
            return False
        else:
            return False
        return result.returncode == 0
    except Exception:
        return False

def is_device_in_range(target_mac: str, duration: int = 4) -> Optional[bool]:
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
    except BluetoothScanError:
        # Unknown is not the same as absent. Do not count scanner failures
        # toward the lock threshold.
        return None

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
        self._armed_evt = threading.Event()
        self._armed_evt.set()
        self._paused_until = 0
        self._running = False
        self.last_seen = 0  # Timestamp of last successful detection

    def stop(self):
        self._stop_evt.set()

    def stopped(self):
        return self._stop_evt.is_set()

    def resume(self):
        """Re-arm only after an explicit command and a positive device scan."""
        if self.stopped():
            return False, "Monitor is stopped. Start it again first."
        if self._armed_evt.is_set():
            return False, "Monitor is already armed."
        remaining = int(self._paused_until - time.time())
        if remaining > 0:
            return False, f"Safety pause is active for {remaining}s more; monitor remains disarmed."
        result = is_device_in_range(self.phone_mac, duration=self.scan_duration)
        if result is None:
            return False, "Bluetooth scan failed; monitor remains disarmed."
        if not result:
            return False, "Configured phone was not detected; monitor remains disarmed."
        self._armed_evt.set()
        return True, "Phone detected. Automatic locking re-armed."

    def run(self):
        self._running = True
        consecutive_misses = 0
        # Main loop
        while not self.stopped():
            if not self._armed_evt.wait(timeout=0.5):
                continue
            if self.stopped():
                break
            # If paused due to recent lock/unlock, skip checks
            if time.time() < self._paused_until:
                time.sleep(self.poll_interval)
                continue

            try:
                in_range = is_device_in_range(self.phone_mac, duration=self.scan_duration)
            except Exception:
                in_range = None

            # A stop request received during a blocking Bluetooth scan must
            # prevent that scan's result from triggering a lock.
            if self.stopped():
                break

            if not in_range:
                if in_range is None:
                    consecutive_misses = 0
                    print("\033[33m[!] Bluetooth scan failed; this check will not count as a device miss.\033[0m")
                    self._stop_evt.wait(self.poll_interval)
                    continue
                consecutive_misses += 1
                print(f"\033[33m[!] Device not detected ({consecutive_misses}/{self.safety_threshold})\033[0m")
                if consecutive_misses >= self.safety_threshold:
                    print("\033[31m[!] Device absent for threshold — locking system now.\033[0m")
                    lock_succeeded = lock_system()
                    if not lock_succeeded:
                        print("\033[31m[!] Lock command failed. Monitor is disarmed to prevent a lock loop; use 'resume' after resolving the issue.\033[0m")
                    else:
                        print("\033[33m[!] Monitor disarmed after lock. Unlock the computer, then run 'resume' to verify the phone and re-arm.\033[0m")
                    self._armed_evt.clear()
                    # Keep the configured delay as a minimum before a manual re-arm.
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

