import argparse
import bluetooth
from proximity_lock_system.config import load_config, save_config, delete_config
from proximity_lock_system.core import monitor_connection

def scan_devices():
    """Scan and display nearby Bluetooth devices."""
    print("🔍 Scanning for nearby Bluetooth devices (5s)...")
    devices = bluetooth.discover_devices(duration=5, lookup_names=True)
    if not devices:
        print("⚠️ No Bluetooth devices found. Please ensure Bluetooth is enabled.")
        return None

    for i, (mac, name) in enumerate(devices, 1):
        print(f"{i}. {name or 'Unknown'} ({mac})")

    choice = int(input("Select your device (number): ").strip())
    if choice < 1 or choice > len(devices):
        print("❌ Invalid choice.")
        return None

    return devices[choice - 1]  # (mac, name)

def setup():
    """Interactive setup for new users."""
    print("🔧 Proximity Lock System Setup Wizard")

    selected = scan_devices()
    if not selected:
        print("❌ Setup failed — no device selected.")
        return
    mac, name = selected

    interval = int(input("Enter polling interval (in seconds, e.g., 5): ").strip())
    pause_duration = int(input("Enter pause duration after manual unlock (seconds, e.g., 180): ").strip())

    save_config({
        "PHONE_MAC": mac,
        "DEVICE_NAME": name,
        "POLL_INTERVAL": interval,
        "PAUSE_AFTER_UNLOCK": pause_duration
    })
    print(f"\n✅ Configuration saved! Device: {name} ({mac})")

def start():
    """Start monitoring."""
    config = load_config()
    if not config:
        print("⚠️ No configuration found. Run `proximity-lock setup` first.")
        return

    monitor_connection(
        phone_mac=config["PHONE_MAC"],
        poll_interval=config["POLL_INTERVAL"],
        pause_after_unlock=config["PAUSE_AFTER_UNLOCK"]
    )

def reset():
    confirm = input("⚠️ Reset configuration? (y/n): ").strip().lower()
    if confirm == "y":
        delete_config()
        print("✅ Configuration reset.")
    else:
        print("❌ Operation cancelled.")

def show_help():
    print("""
🧭 Proximity Lock CLI Commands:
  proximity-lock setup   → Configure your Bluetooth device
  proximity-lock start   → Start monitoring
  proximity-lock reset   → Reset configuration
  proximity-lock help    → Show this help
""")

def main():
    parser = argparse.ArgumentParser(description="Proximity Lock System CLI")
    parser.add_argument("command", help="Command to run (setup/start/reset/help)")
    args = parser.parse_args()
    cmd = args.command.lower()

    if cmd == "setup":
        setup()
    elif cmd == "start":
        start()
    elif cmd == "reset":
        reset()
    elif cmd == "help":
        show_help()
    else:
        print("❌ Unknown command. Use `proximity-lock help`.")

if __name__ == "__main__":
    main()
