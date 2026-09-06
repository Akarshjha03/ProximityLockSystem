# proximity_lock_system/cli.py
"""
Interactive REPL for the macOS Proximity Lock System.

Commands
--------
  scan               Discover nearby BLE devices (CoreBluetooth)
  set-device <num>   Save a device from the last scan
  start              Start background BLE proximity monitor
  stop               Stop monitoring
  status             Show current monitor state and config
  reset              Clear saved configuration
  help               List commands
  exit / quit        Stop monitoring and exit
"""

import sys
import threading
import time

from proximity_lock_system import __version__
from proximity_lock_system.config import load_config, save_config, reset_config
from proximity_lock_system.utils import discover_nearby_devices
from proximity_lock_system.core import MonitorThread

# ── ANSI colours ──────────────────────────────────────────────────────────────
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
CYAN   = "\033[36m"
RESET  = "\033[0m"

BANNER = f"""
{YELLOW}██████╗ ██████╗  ██████╗ ██╗  ██╗██╗███╗   ███╗██╗████████╗██╗   ██╗
██╔══██╗██╔══██╗██╔═══██╗╚██╗██╔╝██║████╗ ████║██║╚══██╔══╝╚██╗ ██╔╝
██████╔╝██████╔╝██║   ██║ ╚███╔╝ ██║██╔████╔██║██║   ██║    ╚████╔╝ 
██╔═══╝ ██╔══██╗██║   ██║ ██╔██╗ ██║██║╚██╔╝██║██║   ██║     ╚██╔╝  
██║     ██║  ██║╚██████╔╝██╔╝ ██╗██║██║ ╚═╝ ██║██║   ██║      ██║   
╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚═╝   ╚═╝      ╚═╝   
{RESET}
{CYAN}Proximity Lock System — macOS Edition  v{__version__}{RESET}
{CYAN}Bluetooth engine: bleak (CoreBluetooth / BLE){RESET}
Type 'help' for available commands.
"""

PROMPT = f"{CYAN}proximity-lock> {RESET}"

# ── Global monitor state ──────────────────────────────────────────────────────
_monitor: MonitorThread | None = None
_monitor_lock = threading.Lock()

# ── Banner ────────────────────────────────────────────────────────────────────

def print_banner():
    print(BANNER)
    cfg = load_config()
    phone_id = cfg.get("PHONE_MAC")
    device_name = cfg.get("DEVICE_NAME")
    if phone_id:
        label = device_name if device_name else "Unknown Device"
        print(f"{CYAN}Last configured device: {label}  [{phone_id}]{RESET}\n")
    else:
        print(f"{YELLOW}No device configured. Run 'scan' to find your phone.{RESET}\n")

# ── Help ──────────────────────────────────────────────────────────────────────

def cmd_help():
    print(f"""
{CYAN}Available commands:{RESET}
  {GREEN}scan{RESET}                 - Discover nearby BLE devices via CoreBluetooth
  {GREEN}set-device <num>{RESET}    - Select a device from the last scan
  {GREEN}start{RESET}                - Start background BLE proximity monitoring
  {GREEN}stop{RESET}                 - Stop monitoring
  {GREEN}status{RESET}               - Show monitor status and configuration
  {GREEN}reset{RESET}                - Clear saved configuration
  {GREEN}help{RESET}                 - Show this help
  {GREEN}exit{RESET} / {GREEN}quit{RESET}        - Stop monitoring and exit

{YELLOW}Note:{RESET} On macOS, CoreBluetooth exposes UUIDs instead of hardware MAC addresses.
The UUID stored in config is stable per device per Mac.
""")

# ── In-memory scan cache ──────────────────────────────────────────────────────
_last_scan: list = []

# ── Commands ──────────────────────────────────────────────────────────────────

def command_scan():
    global _last_scan
    cfg = load_config()
    duration = cfg.get("SCAN_DURATION", 5)
    print(f"{YELLOW}Scanning for nearby BLE devices ({duration}s) — ensure your phone's Bluetooth is on...{RESET}")
    devices = discover_nearby_devices(duration=duration)
    _last_scan = devices
    if not devices:
        print(f"{RED}No devices found.  Make sure:{RESET}")
        print("  • Your phone's Bluetooth is enabled and not in airplane mode.")
        print("  • macOS Bluetooth is on (System Settings → Bluetooth).")
        print("  • Terminal has Bluetooth permission (System Settings → Privacy & Security → Bluetooth).")
        return
    print(f"{GREEN}Found {len(devices)} device(s):{RESET}")
    for i, (device_id, name) in enumerate(devices):
        print(f"  [{i}] {name:<30}  {device_id}")


def command_set_device(tokens: list):
    global _last_scan
    if not _last_scan:
        print(f"{YELLOW}No previous scan results. Run 'scan' first.{RESET}")
        return
    if len(tokens) < 2:
        print(f"{YELLOW}Usage: set-device <number>{RESET}")
        return
    try:
        idx = int(tokens[1])
        device_id, name = _last_scan[idx]
        cfg = load_config()
        cfg["PHONE_MAC"] = device_id
        cfg["DEVICE_NAME"] = name
        save_config(cfg)
        print(f"{GREEN}Device saved: {name}  [{device_id}]{RESET}")
    except (ValueError, IndexError):
        print(f"{RED}Invalid selection. Choose a number shown by 'scan'.{RESET}")


def start_monitor():
    global _monitor
    with _monitor_lock:
        if _monitor and not _monitor.stopped():
            print(f"{YELLOW}Monitor is already running.{RESET}")
            return
        cfg = load_config()
        phone_id = cfg.get("PHONE_MAC")
        if not phone_id:
            print(f"{YELLOW}No device configured. Run 'scan' then 'set-device <num>'.{RESET}")
            return
        poll      = cfg.get("POLL_INTERVAL", 10)
        pause     = cfg.get("UNLOCK_PAUSE", 180)
        threshold = cfg.get("SAFETY_THRESHOLD", 2)
        scan_dur  = cfg.get("SCAN_DURATION", 5)
        _monitor = MonitorThread(
            phone_mac=phone_id,
            poll_interval=poll,
            pause_after_unlock=pause,
            safety_threshold=threshold,
            scan_duration=scan_dur,
        )
        _monitor.start()
        name = cfg.get("DEVICE_NAME") or phone_id
        print(
            f"{GREEN}Monitor started for '{name}'\n"
            f"  interval={poll}s  safety_threshold={threshold}  "
            f"post-lock pause={pause}s{RESET}"
        )


def stop_monitor():
    global _monitor
    with _monitor_lock:
        if not _monitor or _monitor.stopped():
            print(f"{YELLOW}Monitor is not running.{RESET}")
            return
        _monitor.stop()
        for _ in range(15):
            if _monitor.stopped():
                break
            time.sleep(0.2)
        print(f"{GREEN}Monitor stopped.{RESET}")
        _monitor = None


def show_status():
    cfg = load_config()
    phone  = cfg.get("PHONE_MAC") or "<not set>"
    name   = cfg.get("DEVICE_NAME") or "<unknown>"
    poll   = cfg.get("POLL_INTERVAL", 10)
    pause  = cfg.get("UNLOCK_PAUSE", 180)
    thresh = cfg.get("SAFETY_THRESHOLD", 2)
    running = _monitor is not None and not _monitor.stopped()

    print(f"\n{CYAN}── Status ────────────────────────────────────{RESET}")
    print(f"  Device    : {name}")
    print(f"  Identifier: {phone}")
    print(f"  Monitoring: {GREEN}active{RESET}" if running else f"  Monitoring: {YELLOW}stopped{RESET}")

    if running and _monitor and _monitor.last_seen > 0:
        elapsed = int(time.time() - _monitor.last_seen)
        ts = time.strftime("%H:%M:%S", time.localtime(_monitor.last_seen))
        print(f"  Last seen : {GREEN}{ts} ({elapsed}s ago){RESET}")
    elif running:
        print(f"  Last seen : {YELLOW}not yet detected since start{RESET}")

    print(f"  Interval  : {poll}s   Pause after lock: {pause}s   Safety threshold: {thresh}")
    print(f"{CYAN}──────────────────────────────────────────────{RESET}\n")


def reset_config_command():
    confirm = input("Reset configuration? This removes your saved device. (y/n): ").strip().lower()
    if confirm == "y":
        reset_config()
        print(f"{GREEN}Configuration reset.{RESET}")
    else:
        print("Cancelled.")

# ── REPL loop ─────────────────────────────────────────────────────────────────

def repl():
    print_banner()
    while True:
        try:
            cmdline = input(PROMPT).strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting…")
            stop_monitor()
            sys.exit(0)

        if not cmdline:
            continue

        tokens = cmdline.split()
        cmd = tokens[0].lower()

        if cmd == "help":
            cmd_help()
        elif cmd == "scan":
            command_scan()
        elif cmd == "set-device":
            command_set_device(tokens)
        elif cmd == "start":
            start_monitor()
        elif cmd == "stop":
            stop_monitor()
        elif cmd == "status":
            show_status()
        elif cmd == "reset":
            reset_config_command()
        elif cmd in ("exit", "quit"):
            stop_monitor()
            print("Goodbye.")
            sys.exit(0)
        else:
            print(f"{YELLOW}Unknown command: '{cmd}'. Type 'help' for commands.{RESET}")


def main():
    try:
        repl()
    except Exception as e:
        print(f"{RED}Fatal error: {e}{RESET}")
        stop_monitor()
        raise


if __name__ == "__main__":
    main()
