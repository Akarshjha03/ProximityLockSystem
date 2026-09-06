# proximity_lock_system/core.py
"""
Core monitoring engine for macOS.

lock_system() tries three methods in priority order:
  1. osascript Cmd+Ctrl+Q  — native Lock Screen keyboard shortcut (macOS 10.13+).
     Most reliable: no path issues, no "Require password" setting dependency.
  2. pmset displaysleepnow — display sleep; lock activates when "Require password
     immediately after sleep" is enabled (macOS default since Ventura).
  3. CGSession -suspend    — legacy; binary path varies between macOS releases.
"""

import os
import platform
import subprocess
import time
import threading

from .utils import discover_nearby_devices
from .config import load_config

# ── CGSession binary paths (checked in order) ─────────────────────────────────
_CGSESSION_PATHS = [
    "/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession",
    "/System/Library/CoreServices/loginwindow.app/Contents/MacOS/loginwindow",
]


# ── Lock command ──────────────────────────────────────────────────────────────

def lock_system() -> str:
    """
    Lock the screen using the best available method.

    Returns the method name that succeeded ('osascript', 'pmset', 'CGSession',
    or 'failed').  The caller/menu bar uses this to emit an accurate log entry.

    macOS method priority
    ---------------------
    1. osascript   — simulates Cmd+Ctrl+Q (native Lock Screen shortcut).
                     Works without any System Settings dependency.
    2. pmset       — display sleep; the lock screen appears on wake when
                     "Require password immediately" is on (macOS default).
    3. CGSession   — legacy suspend; binary location changes per release.
    """
    os_name = platform.system()

    # ── Windows ───────────────────────────────────────────────────────────────
    if os_name == "Windows":
        try:
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"],
                           check=False, shell=True, timeout=5)
        except Exception:
            pass
        return "rundll32"

    # ── Linux ─────────────────────────────────────────────────────────────────
    if os_name == "Linux":
        for cmd in ("gnome-screensaver-command -l",
                    "loginctl lock-session",
                    "xdg-screensaver lock"):
            try:
                subprocess.run(cmd, shell=True, check=False, timeout=5)
            except Exception:
                pass
        return "xdg/loginctl"

    # ── macOS ─────────────────────────────────────────────────────────────────
    if os_name != "Darwin":
        return "unsupported"

    # Method 1 — osascript Cmd+Ctrl+Q (confirmed working on this machine)
    try:
        result = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to keystroke "q" '
             'using {command down, control down}'],
            check=False, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return "osascript"
    except Exception:
        pass

    # Method 2 — pmset displaysleepnow
    try:
        result = subprocess.run(
            ["pmset", "displaysleepnow"],
            check=False, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return "pmset"
    except Exception:
        pass

    # Method 3 — CGSession (legacy, path varies)
    for path in _CGSESSION_PATHS:
        try:
            if os.path.exists(path):
                subprocess.run([path, "-suspend"], check=False, timeout=5)
                return "CGSession"
        except Exception:
            continue

    return "failed"


# ── Device proximity check ────────────────────────────────────────────────────

def is_device_in_range(target_id: str, duration: int = 4) -> bool:
    """
    Return True if *target_id* (CoreBluetooth UUID or classic MAC) is found
    among nearby BLE devices within *duration* seconds.

    Comparison is case-insensitive to handle UUID/MAC capitalisation variants.
    """
    try:
        found = discover_nearby_devices(duration=duration)
        target_lower = target_id.lower()
        for device_id, _ in found:
            if device_id and device_id.lower() == target_lower:
                return True
        return False
    except Exception:
        return False


# ── Monitor thread ────────────────────────────────────────────────────────────

class MonitorThread(threading.Thread):
    """
    Background daemon thread that polls BLE proximity and locks macOS when
    the paired device leaves range beyond the configured safety threshold.

    Public attributes (read by menu bar ticker without locking)
    -----------------------------------------------------------
    last_seen        : float  — unix timestamp of last successful BLE detection
    consecutive_misses: int   — current miss streak
    paused_until     : float  — unix timestamp when the post-lock cooldown ends

    Lifecycle
    ---------
    start()   → begins the monitoring loop
    stop()    → signals the loop to exit
    stopped() → True after stop() has been called
    """

    def __init__(
        self,
        phone_mac: str,
        poll_interval: int,
        pause_after_unlock: int,
        safety_threshold: int,
        scan_duration: int,
    ):
        super().__init__(daemon=True)
        self.phone_mac          = phone_mac
        self.poll_interval      = max(1, int(poll_interval))
        self.pause_after_unlock = max(0, int(pause_after_unlock))
        self.safety_threshold   = max(1, int(safety_threshold))
        self.scan_duration      = max(1, int(scan_duration))

        self._stop_evt = threading.Event()
        # Public live state — read by menu bar ticker
        self.last_seen:          float = 0.0
        self.consecutive_misses: int   = 0
        self.paused_until:       float = 0.0
        self.last_lock_method:   str   = ""   # which method fired last lock
        self._running = False

    # ── Control ───────────────────────────────────────────────────────────────

    def stop(self):
        self._stop_evt.set()

    def stopped(self) -> bool:
        return self._stop_evt.is_set()

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        self._running = True
        self.consecutive_misses = 0

        while not self.stopped():

            # Cooldown: stay quiet after a lock event
            if time.time() < self.paused_until:
                remaining = int(self.paused_until - time.time())
                print(f"\033[36m[~] Post-lock cooldown — {remaining}s remaining\033[0m")
                self._sleep(self.poll_interval)
                continue

            # BLE proximity scan
            try:
                in_range = is_device_in_range(self.phone_mac,
                                              duration=self.scan_duration)
            except Exception:
                in_range = False

            if not in_range:
                self.consecutive_misses += 1
                print(
                    f"\033[33m[!] Device not detected "
                    f"({self.consecutive_misses}/{self.safety_threshold})\033[0m"
                )
                if self.consecutive_misses >= self.safety_threshold:
                    print("\033[31m[!] Device out of range — locking screen now.\033[0m")
                    method = lock_system()
                    self.last_lock_method = method
                    print(f"\033[31m    Lock triggered via: {method}\033[0m")
                    self.paused_until       = time.time() + self.pause_after_unlock
                    self.consecutive_misses = 0
            else:
                if self.consecutive_misses > 0:
                    print("\033[32m[+] Device back in range — resetting counter.\033[0m")
                self.last_seen          = time.time()
                self.consecutive_misses = 0

            self._sleep(self.poll_interval)

        self._running = False

    def _sleep(self, seconds: int):
        """Sleep in 1-second steps so stop() is responsive."""
        for _ in range(max(1, seconds)):
            if self.stopped():
                break
            time.sleep(1)
