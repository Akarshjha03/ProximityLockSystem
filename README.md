# Proximity Lock System

Automatically locks your desktop when your phone moves out of Bluetooth range.

## Requirements
- Python 3.8 or newer
- A working Bluetooth adapter on the host machine
- Platform-specific lock utilities (usually present by default)
  - Windows: built-in LockWorkStation
  - macOS: CGSession or other locking utilities
  - Linux: GNOME `gnome-screensaver` or other lock commands

## Installation
1. Open a terminal or PowerShell in the project directory.
2. (Optional) Create and activate a virtual environment:

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
```

3. Install dependencies from `requirements.txt`:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Note: On Windows, `requirements.txt` references `pybluez` and a Windows-friendly `pybluez-win10` option. If you have trouble installing the library from PyPI, consider installing from the project's GitHub or using the `pybluez-win10` wheel.

## Usage
After installation, run the CLI to set up monitoring:

```powershell
# From project root
python -m proximity_lock_system.cli
# or (if installed via setup.py) use the console script
proximity-lock
```

The CLI will scan for nearby Bluetooth devices and prompt you to choose your phone. Once selected, it will monitor the device and lock the system when the phone has been out of range for the configured threshold.

## Platform notes
- Windows: The tool uses `rundll32.exe user32.dll,LockWorkStation` to lock the session. No extra packages are required.
- macOS: Uses `CGSession -suspend`. If that doesn't work on newer macOS versions, consider running an AppleScript or `osascript` command to lock the screen.
- Linux: Calls `gnome-screensaver-command -l` (GNOME). If you use another DE, replace the command with one that works for your environment (for example `loginctl lock-session`, `dm-tool lock`, or other `xdg` alternatives).

## Configuration
Tweak the constants in `proximity_lock_system/config.py`:
- `POLL_INTERVAL` — seconds between checks
- `UNLOCK_PAUSE` — pause after manual unlock (seconds)
- `SAFETY_THRESHOLD` — consecutive misses before locking
- `SCAN_DURATION` — seconds per Bluetooth scan

## Troubleshooting
- No devices found: ensure your phone's Bluetooth is turned on and discoverable.
- Permission/adapter errors: ensure the OS user has permission to access Bluetooth and that the adapter is enabled.
- Lock not working on Linux/macOS: the project uses a DE-specific command; update `proximity_lock_system/core.py` to call a command available on your system.

## Contributing
PRs welcome. If adding OS support, please include testing notes and required dependencies.

## License
See `PKG-INFO` or project metadata.
