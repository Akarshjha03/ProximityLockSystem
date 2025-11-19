# proximity_lock_system/cli.py
import sys
import threading
import time
from proximity_lock_system import __version__
from proximity_lock_system.config import load_config, save_config, reset_config
from proximity_lock_system.utils import discover_nearby_devices
from proximity_lock_system.core import MonitorThread

# ANSI color helpers
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
RESET = "\033[0m"

BANNER = f"""
{YELLOW}  ____                 _                 _   _      _ _
██████╗ ██████╗  ██████╗ ██╗  ██╗██╗███╗   ███╗██╗████████╗██╗   ██╗
██╔══██╗██╔══██╗██╔═══██╗╚██╗██╔╝██║████╗ ████║██║╚══██╔══╝╚██╗ ██╔╝
██████╔╝██████╔╝██║   ██║ ╚███╔╝ ██║██╔████╔██║██║   ██║    ╚████╔╝ 
██╔═══╝ ██╔══██╗██║   ██║ ██╔██╗ ██║██║╚██╔╝██║██║   ██║     ╚██╔╝  
██║     ██║  ██║╚██████╔╝██╔╝ ██╗██║██║ ╚═╝ ██║██║   ██║      ██║   
╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚═╝   ╚═╝      ╚═╝   
                                                                    
{RESET}
{CYAN}Proximity Lock System — Security Edition v{__version__}{RESET}
Type 'help' for commands.
"""

PROMPT = f"{CYAN}proximity-lock> {RESET}"

# Global monitor reference
_monitor: MonitorThread = None
_monitor_lock = threading.Lock()

def print_banner():
    print(BANNER)

def cmd_help():
    print(f"""
{CYAN}Available commands:{RESET}
  {GREEN}scan{RESET}                 - Discover nearby Bluetooth devices
  {GREEN}set-device <num>{RESET}    - Select device from last scan results
  {GREEN}start{RESET}                - Start background proximity monitoring
  {GREEN}stop{RESET}                 - Stop background monitoring
  {GREEN}status{RESET}               - Show monitor status and config
  {GREEN}reset{RESET}                - Reset saved configuration
  {GREEN}help{RESET}                 - Show this help
  {GREEN}exit{RESET} / {GREEN}quit{RESET} - Exit the tool
""")

# In-memory last scan results
_last_scan = []

def command_scan():
    global _last_scan
    cfg = load_config()
    duration = cfg.get("SCAN_DURATION", 5)
    print(f"{YELLOW}Scanning for nearby Bluetooth devices ({duration}s)...{RESET}")
    devices = discover_nearby_devices(duration=duration)
    _last_scan = devices
    if not devices:
        print(f"{RED}No devices found. Ensure Bluetooth is enabled and your phone is discoverable.{RESET}")
        return
    for i, (mac, name) in enumerate(devices):
        print(f"  [{i}] {name} ({mac})")

def command_set_device(tokens):
    global _last_scan
    if not _last_scan:
        print(f"{YELLOW}No previous scan results. Run 'scan' first.{RESET}")
        return
    if len(tokens) < 2:
        print(f"{YELLOW}Usage: set-device <number>{RESET}")
        return
    try:
        idx = int(tokens[1])
        mac, name = _last_scan[idx]
        cfg = load_config()
        cfg["PHONE_MAC"] = mac
        cfg["DEVICE_NAME"] = name
        save_config(cfg)
        print(f"{GREEN}Device saved: {name} ({mac}){RESET}")
    except (ValueError, IndexError):
        print(f"{RED}Invalid selection.{RESET}")

def start_monitor():
    global _monitor
    with _monitor_lock:
        if _monitor and not _monitor.stopped():
            print(f"{YELLOW}Monitor already running.{RESET}")
            return
        cfg = load_config()
        phone_mac = cfg.get("PHONE_MAC")
        if not phone_mac:
            print(f"{YELLOW}No device configured. Run 'scan' then 'set-device'.{RESET}")
            return
        poll = cfg.get("POLL_INTERVAL", 10)
        pause = cfg.get("UNLOCK_PAUSE", 180)
        threshold = cfg.get("SAFETY_THRESHOLD", 2)
        scan_dur = cfg.get("SCAN_DURATION", 5)
        _monitor = MonitorThread(phone_mac=phone_mac,
                                 poll_interval=poll,
                                 pause_after_unlock=pause,
                                 safety_threshold=threshold,
                                 scan_duration=scan_dur)
        _monitor.start()
        print(f"{GREEN}Monitor started for {phone_mac} (interval={poll}s, pause={pause}s).{RESET}")

def stop_monitor():
    global _monitor
    with _monitor_lock:
        if not _monitor or _monitor.stopped():
            print(f"{YELLOW}Monitor is not running.{RESET}")
            return
        _monitor.stop()
        # wait a short time for thread to exit
        for _ in range(10):
            if _monitor.stopped():
                break
            time.sleep(0.2)
        print(f"{GREEN}Monitor stopped.{RESET}")
        _monitor = None

def show_status():
    cfg = load_config()
    phone = cfg.get("PHONE_MAC") or "<not set>"
    name = cfg.get("DEVICE_NAME") or "<unknown>"
    poll = cfg.get("POLL_INTERVAL", 10)
    pause = cfg.get("UNLOCK_PAUSE", 180)
    threshold = cfg.get("SAFETY_THRESHOLD", 2)
    running = _monitor is not None and not _monitor.stopped()
    print(f"{CYAN}Status:{RESET}")
    print(f"  Device: {name} ({phone})")
    print(f"  Monitoring: {GREEN if running else YELLOW}{running}{RESET}")
    print(f"  Interval: {poll}s  Pause after lock: {pause}s  Safety threshold: {threshold}")

def reset_config_command():
    confirm = input("Are you sure you want to reset configuration? (y/n): ").strip().lower()
    if confirm == "y":
        reset_config()
        print(f"{GREEN}Configuration reset.{RESET}")
    else:
        print("Cancelled.")

def repl():
    print_banner()
    while True:
        try:
            cmdline = input(PROMPT).strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
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
            print(f"{YELLOW}Unknown command: {cmd}. Type 'help' for commands.{RESET}")

def main():
    try:
        repl()
    except Exception as e:
        print(f"{RED}Fatal error: {e}{RESET}")
        stop_monitor()
        raise

if __name__ == "__main__":
    main()
