# proximity_lock_system/menubar.py
"""
macOS Menu Bar (Status Bar) App — Proximity Lock System
Real-time BLE proximity monitoring with live activity log.

Architecture notes
------------------
• All rumps UI calls MUST run on the main thread.
  Background work (BLE scan, MonitorThread) dispatches back via libdispatch.
• A 2-second rumps.Timer drives the live status section and log refresh.
• Events are captured by watching MonitorThread state changes in _tick(),
  appended to a collections.deque, shown in the menu, and written to
  ~/.proximity_lock.log for persistent history.
"""

import os
import time
import threading
import collections
import datetime

import rumps
from libdispatch import dispatch_async, dispatch_get_main_queue

from .config import load_config, save_config
from .utils import discover_nearby_devices
from .core import MonitorThread

# ── Asset paths ───────────────────────────────────────────────────────────────
_HERE   = os.path.dirname(os.path.abspath(__file__))
_ASSETS = os.path.join(_HERE, "..", "assets")
ICON_NORMAL = os.path.join(_ASSETS, "iconTemplate.png")

# ── Log file path ─────────────────────────────────────────────────────────────
LOG_PATH       = os.path.expanduser("~/.proximity_lock.log")
MAX_LOG_LINES  = 500        # lines kept in file
MAX_MENU_LINES = 5          # events shown in the menu

# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")

def _fmt_ago(ts: float) -> str:
    if ts == 0:
        return "never"
    secs = int(time.time() - ts)
    if secs < 60:
        return f"{secs}s ago"
    return f"{secs // 60}m {secs % 60}s ago"

def _run_on_main(fn):
    """Dispatch a zero-arg callable to the macOS main thread."""
    dispatch_async(dispatch_get_main_queue(), fn)

def _write_log(line: str):
    """Append one line to the persistent log file (best-effort)."""
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

# ── App ───────────────────────────────────────────────────────────────────────

class ProximityLockApp(rumps.App):

    def __init__(self):
        self._cfg          = load_config()
        self._monitor: MonitorThread | None = None
        self._monitor_lock = threading.Lock()
        self._last_scan:   list  = []
        self._scan_in_progress   = False

        # ── Activity log ──────────────────────────────────────────────────────
        # Each entry: (timestamp_str, icon_char, message)
        self._log: collections.deque = collections.deque(maxlen=MAX_LOG_LINES)
        # Snapshot of monitor state used to detect changes in _tick()
        self._prev_last_seen:    float = 0.0
        self._prev_misses:       int   = 0
        self._prev_paused_until: float = 0.0
        self._prev_running:      bool  = False

        # ── Live status menu items ─────────────────────────────────────────────
        self._item_state    = rumps.MenuItem("● Idle",         callback=None)
        self._item_device   = rumps.MenuItem("Device: —",      callback=None)
        self._item_seen     = rumps.MenuItem("Last seen: —",   callback=None)
        self._item_misses   = rumps.MenuItem("Misses: 0",      callback=None)
        self._item_cooldown = rumps.MenuItem("",               callback=None)

        for item in (self._item_state, self._item_device,
                     self._item_seen, self._item_misses, self._item_cooldown):
            item.set_callback(None)

        # ── Log section header + 5 rolling rows ───────────────────────────────
        self._item_log_hdr  = rumps.MenuItem("─── Recent Activity ───", callback=None)
        self._item_log_hdr.set_callback(None)
        self._log_items = [
            rumps.MenuItem("", callback=None) for _ in range(MAX_MENU_LINES)
        ]
        for li in self._log_items:
            li.set_callback(None)

        # ── Action buttons ────────────────────────────────────────────────────
        self._btn_start    = rumps.MenuItem("▶  Start Monitoring",  callback=self.start_monitoring)
        self._btn_stop     = rumps.MenuItem("■  Stop Monitoring",   callback=self.stop_monitoring)
        self._btn_scan     = rumps.MenuItem("⟳  Scan Devices",      callback=self.scan_devices)
        self._btn_view_log = rumps.MenuItem("📋  View Full Log",    callback=self.view_full_log)
        self._btn_test     = rumps.MenuItem("🔒  Test Lock Now",    callback=self.test_lock_now)

        super().__init__(
            name        = "ProximityLock",
            icon        = ICON_NORMAL,
            menu        = [
                # live status ──────────────────────────────────────────────────
                self._item_state,
                self._item_device,
                self._item_seen,
                self._item_misses,
                self._item_cooldown,
                None,
                # actions ──────────────────────────────────────────────────────
                self._btn_start,
                self._btn_stop,
                self._btn_test,
                None,
                self._btn_scan,
                None,
                # activity log ─────────────────────────────────────────────────
                self._item_log_hdr,
                *self._log_items,
                self._btn_view_log,
                None,
                self._build_prefs_menu(),
                None,
            ],
            quit_button = "Quit",
        )

        self._mark_icon_as_template()
        self._push_log("ℹ️", "App launched")
        self._refresh_ui()

        self._ticker = rumps.Timer(self._tick, 2)
        self._ticker.start()

    # ── Template icon ─────────────────────────────────────────────────────────

    def _mark_icon_as_template(self):
        """setTemplate_(True) → auto white/black for dark/light mode."""
        try:
            btn   = self._status_item.button()
            image = btn.image()
            if image is not None:
                image.setTemplate_(True)
                btn.setImage_(image)
        except Exception:
            pass

    # ── Activity log helpers ──────────────────────────────────────────────────

    def _push_log(self, icon: str, msg: str):
        """Append an event to the in-memory log and the file."""
        ts   = _now()
        line = f"[{ts}] {icon}  {msg}"
        self._log.appendleft(line)   # newest first
        _write_log(line)

    def _refresh_log_items(self):
        """Update the 5 rolling menu rows from self._log."""
        entries = list(self._log)
        for i, li in enumerate(self._log_items):
            li.title = f"  {entries[i]}" if i < len(entries) else ""

    # ── 2-second tick ─────────────────────────────────────────────────────────

    def _tick(self, _sender):
        """Detect state changes, emit log events, then refresh the UI."""
        mon     = self._monitor
        running = mon is not None and not mon.stopped()

        # ── Monitor started / stopped ──────────────────────────────────────────
        if running != self._prev_running:
            if running:
                cfg  = load_config()
                name = cfg.get("DEVICE_NAME") or cfg.get("PHONE_MAC") or "device"
                self._push_log("▶️", f"Monitoring started — watching {name}")
            else:
                self._push_log("■", "Monitoring stopped")
            self._prev_running = running

        if running and mon:
            # ── Device detected (last_seen advanced) ───────────────────────────
            if mon.last_seen > self._prev_last_seen and self._prev_last_seen > 0:
                if self._prev_misses > 0:
                    self._push_log("✅", f"Device back in range (after {self._prev_misses} miss(es))")
                else:
                    self._push_log("📶", "Device detected")
            self._prev_last_seen = mon.last_seen

            # ── Miss counter increased ─────────────────────────────────────────
            cur_misses = mon.consecutive_misses
            if cur_misses > self._prev_misses:
                cfg    = load_config()
                thresh = cfg.get("SAFETY_THRESHOLD", 2)
                self._push_log("⚠️", f"Device not found ({cur_misses}/{thresh} misses)")
            self._prev_misses = cur_misses

            # ── Lock triggered (paused_until just increased) ───────────────────
            if mon.paused_until > self._prev_paused_until and self._prev_paused_until >= 0:
                method    = getattr(mon, "last_lock_method", "?") or "?"
                resume_at = time.strftime("%H:%M:%S", time.localtime(mon.paused_until))
                self._push_log("🔒", f"Screen LOCKED via {method} — cooldown until {resume_at}")
                # macOS notification so user knows even after unlock
                _run_on_main(lambda: rumps.notification(
                    "Proximity Lock", "🔒 Screen Locked",
                    f"Device left range. Cooldown until {resume_at}.",
                    sound=True,
                ))
            self._prev_paused_until = mon.paused_until

            # ── Cooldown ended ─────────────────────────────────────────────────
            was_cooling = self._prev_paused_until > 0 and \
                          time.time() > self._prev_paused_until + 1
            # (handled implicitly; lock event is the main signal)

        self._refresh_log_items()
        self._refresh_ui()

    # ── Full UI refresh ───────────────────────────────────────────────────────

    def _refresh_ui(self):
        cfg     = load_config()
        running = self._monitor is not None and not self._monitor.stopped()
        mon     = self._monitor

        # title bar
        if running and mon:
            self.title = f"  {_fmt_ago(mon.last_seen)}" if mon.last_seen > 0 else "  scanning…"
        else:
            self.title = ""

        # state badge
        if running:
            if mon and time.time() < mon.paused_until:
                remaining = int(mon.paused_until - time.time())
                self._item_state.title = f"🟡 Cooldown — {remaining}s remaining"
            else:
                self._item_state.title = "🟢 Monitoring Active"
        else:
            self._item_state.title = "🔴 Monitoring Stopped"

        # device
        self._item_device.title = f"Device: {cfg.get('DEVICE_NAME') or '—'}"

        # last seen
        if running and mon and mon.last_seen > 0:
            self._item_seen.title = f"Last seen: {_fmt_ago(mon.last_seen)}"
        elif running:
            self._item_seen.title = "Last seen: not yet detected"
        else:
            self._item_seen.title = "Last seen: —"

        # miss bar
        thresh = cfg.get("SAFETY_THRESHOLD", 2)
        if running and mon:
            misses = mon.consecutive_misses
            bar    = "█" * misses + "░" * max(0, thresh - misses)
            self._item_misses.title = f"Misses: {misses}/{thresh}  [{bar}]"
        else:
            self._item_misses.title = f"Lock threshold: {thresh} missed scans"

        # cooldown sub-line
        if running and mon and time.time() < mon.paused_until:
            remaining = int(mon.paused_until - time.time())
            self._item_cooldown.title = f"   ↳ Screen locked — resumes in {remaining}s"
        else:
            self._item_cooldown.title = ""

        # buttons
        self._btn_start.set_callback(None if running else self.start_monitoring)
        self._btn_stop.set_callback(self.stop_monitoring if running else None)
        self._btn_scan.set_callback(None if self._scan_in_progress else self.scan_devices)

    # ── Commands ──────────────────────────────────────────────────────────────

    @rumps.clicked("▶  Start Monitoring")
    def start_monitoring(self, _=None):
        cfg   = load_config()
        phone = cfg.get("PHONE_MAC")
        if not phone:
            rumps.notification("Proximity Lock", "No Device Configured",
                               "Use '⟳ Scan Devices' first.", sound=False)
            return
        with self._monitor_lock:
            if self._monitor and not self._monitor.stopped():
                return
            self._monitor = MonitorThread(
                phone_mac         = phone,
                poll_interval     = cfg.get("POLL_INTERVAL", 10),
                pause_after_unlock= cfg.get("UNLOCK_PAUSE", 180),
                safety_threshold  = cfg.get("SAFETY_THRESHOLD", 2),
                scan_duration     = cfg.get("SCAN_DURATION", 5),
            )
            self._monitor.start()
        name = cfg.get("DEVICE_NAME") or phone
        rumps.notification("Proximity Lock", "Monitoring Started",
                           f"Watching: {name}", sound=False)
        self._refresh_ui()

    @rumps.clicked("■  Stop Monitoring")
    def stop_monitoring(self, _=None):
        with self._monitor_lock:
            if not self._monitor or self._monitor.stopped():
                return
            self._monitor.stop()
            self._monitor = None
        self._push_log("■", "Monitoring stopped by user")
        rumps.notification("Proximity Lock", "Monitoring Stopped",
                           "Your Mac will no longer auto-lock.", sound=False)
        self._refresh_ui()

    # ── Test lock ─────────────────────────────────────────────────────────────

    @rumps.clicked("🔒  Test Lock Now")
    def test_lock_now(self, _=None):
        """
        Immediately lock the screen so the user can verify the mechanism works.
        Runs lock_system() on a background thread (non-blocking for the UI),
        then logs the result.
        """
        def _do_lock():
            from .core import lock_system
            method = lock_system()
            ts = _now()
            msg = f"Test lock fired via {method}"
            self._push_log("🔒", msg)
            # Show notification after screen unlocks
            _run_on_main(lambda: rumps.notification(
                "Proximity Lock", "🔒 Test Lock Complete",
                f"Method used: {method}. If your screen didn't lock, check "
                "System Settings → Lock Screen → 'Require password'.",
                sound=False,
            ))

        rumps.notification("Proximity Lock", "Locking in 2s…",
                           "Get ready!", sound=False)
        threading.Timer(2.0, _do_lock).start()


    @rumps.clicked("📋  View Full Log")
    def view_full_log(self, _=None):
        entries = list(self._log)
        if not entries:
            rumps.alert(title="Activity Log", message="No events recorded yet.")
            return
        # Show most-recent 30 entries in an alert (rumps limit)
        text = "\n".join(entries[:30])
        if len(entries) > 30:
            text += f"\n\n… and {len(entries)-30} older entries in {LOG_PATH}"
        rumps.alert(title=f"Activity Log  ({len(entries)} events)", message=text)

    # ── Scan ──────────────────────────────────────────────────────────────────

    @rumps.clicked("⟳  Scan Devices")
    def scan_devices(self, _=None):
        if self._scan_in_progress:
            return
        self._scan_in_progress = True
        self._btn_scan.set_callback(None)
        cfg = load_config()
        dur = cfg.get("SCAN_DURATION", 5)
        self._push_log("🔍", f"BLE scan started ({dur}s)")
        rumps.notification("Proximity Lock", "Scanning…",
                           f"Looking for BLE devices ({dur}s).", sound=False)
        threading.Thread(target=self._bg_scan, args=(dur,), daemon=True).start()

    def _bg_scan(self, dur: int):
        """BLE scan — worker thread only."""
        devices = discover_nearby_devices(duration=dur)
        self._last_scan = devices
        self._scan_in_progress = False
        _run_on_main(lambda: self._show_scan_results(devices))  # UI → main thread

    def _show_scan_results(self, devices: list):
        """Called on the main thread after scan finishes."""
        self._push_log("🔍", f"Scan complete — {len(devices)} device(s) found")
        self._refresh_ui()

        if not devices:
            rumps.notification("Proximity Lock", "No Devices Found",
                               "Ensure Bluetooth is on.", sound=False)
            return

        lines = "\n".join(
            f"[{i}]  {name:<28}  {did[:22]}…"
            for i, (did, name) in enumerate(devices[:10])
        )
        # Both calls are now on the MAIN thread ✓
        rumps.alert(title=f"Found {len(devices)} BLE Device(s)",
                    message=lines + "\n\nClose this, then enter the device number below.")

        win = rumps.Window(
            message      = "Enter the number of your phone from the list:",
            title        = "Select Proximity Device",
            default_text = "0",
            ok           = "Save",
            cancel       = "Cancel",
            dimensions   = (240, 22),
        )
        res = win.run()
        if res.clicked:
            try:
                idx      = int(res.text.strip())
                did, name = self._last_scan[idx]
                cfg       = load_config()
                cfg["PHONE_MAC"]   = did
                cfg["DEVICE_NAME"] = name
                save_config(cfg)
                self._cfg = cfg
                self._push_log("💾", f"Device saved: {name}")
                rumps.notification("Proximity Lock", "Device Saved",
                                   f"'{name}' is your proximity key.", sound=False)
                self._refresh_ui()
            except (ValueError, IndexError):
                rumps.notification("Proximity Lock", "Invalid Selection",
                                   "Enter a valid number from the scan list.", sound=False)

    # ── Preferences ───────────────────────────────────────────────────────────

    def _build_prefs_menu(self):
        prefs = rumps.MenuItem("Preferences…")
        sd = rumps.MenuItem("Scan Duration")
        for v in (3, 5, 10, 15):
            item = rumps.MenuItem(f"{v}s", callback=self._set_scan_duration)
            item.state = (v == self._cfg.get("SCAN_DURATION", 5))
            sd.add(item)
        pi = rumps.MenuItem("Poll Interval")
        for v in (5, 10, 20, 30):
            item = rumps.MenuItem(f"{v}s", callback=self._set_poll_interval)
            item.state = (v == self._cfg.get("POLL_INTERVAL", 10))
            pi.add(item)
        st = rumps.MenuItem("Safety Threshold")
        for v in (1, 2, 3, 5):
            item = rumps.MenuItem(f"{v} misses", callback=self._set_safety_threshold)
            item.state = (v == self._cfg.get("SAFETY_THRESHOLD", 2))
            st.add(item)
        prefs.add(sd); prefs.add(pi); prefs.add(st)
        return prefs

    def _set_scan_duration(self, sender):
        v = int(sender.title.rstrip("s"))
        cfg = load_config(); cfg["SCAN_DURATION"] = v; save_config(cfg)
        for item in self.menu["Preferences…"]["Scan Duration"].values():
            item.state = (item.title == sender.title)

    def _set_poll_interval(self, sender):
        v = int(sender.title.rstrip("s"))
        cfg = load_config(); cfg["POLL_INTERVAL"] = v; save_config(cfg)
        for item in self.menu["Preferences…"]["Poll Interval"].values():
            item.state = (item.title == sender.title)

    def _set_safety_threshold(self, sender):
        v = int(sender.title.split()[0])
        cfg = load_config(); cfg["SAFETY_THRESHOLD"] = v; save_config(cfg)
        for item in self.menu["Preferences…"]["Safety Threshold"].values():
            item.state = (item.title == sender.title)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    ProximityLockApp().run()


if __name__ == "__main__":
    main()
