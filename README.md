<p align="center">
  <img src="https://raw.githubusercontent.com/Akarshjha03/ProximityLockSystem/main/Images/Proximity_app_logo.png" alt="Proximity App Logo" width="200" />
</p>

<table align="center">
  <tr>
    <td align="center">
      <a href="https://www.producthunt.com/products/proximity-lock-system?embed=true&utm_source=badge-top-post-badge&utm_medium=badge&utm_source=badge-proximity-lock-system-2-0" target="_blank">
        <img src="https://api.producthunt.com/widgets/embed-image/v1/top-post-badge.svg?post_id=1038161&theme=light&period=daily" width="250" />
      </a>
    </td>
    <td align="center">
      <a href="https://peerlist.io/akarshjha03/project/proximity-lock-system" target="_blank" rel="noreferrer">
        <img
          src="https://peerlist.io/api/v1/projects/embed/PRJHEOG9GNEA8RO9GCRKLNP9K9RJN6?showUpvote=false&theme=light"
          height="72"
        />
      </a>
    </td>
  </tr>
</table>


<p align="center">
  <strong>✨ Featured by <a href="https://x.com/tom_doerr/status/2012322364344664373">Tom Dörr</a> (149k+ followers on X)</strong>
</p>


<h1 align="center">Proximity Lock System</h1>

<p align="center">
  Automatically locks your desktop when your phone moves out of Bluetooth range.
</p>

---

<p align="center">
  <img src="https://raw.githubusercontent.com/Akarshjha03/ProximityLockSystem/main/Images/Terminal_Preview_new.png" width="800" />
</p>

## ⚠️ IMPORTANT WARNING

**Please test this CLI application on virtual machines first before using it on your actual system.**

As we are constantly improving this app and reducing issues, we strongly recommend testing it in a safe environment (like a virtual machine) to ensure it works as expected with your specific setup. Only proceed to use it on your actual system once you feel confident and safe with its behavior.

## Requirements
- Python 3.8 or newer
- A working Bluetooth adapter on the host machine
- Platform-specific lock utilities (usually present by default)
  - Windows: built-in LockWorkStation
  - macOS: CGSession or other locking utilities
  - Linux: GNOME `gnome-screensaver` or other lock commands

## Installation

### Prerequisites
- Python 3.8 or newer

### Install the application

```bash
pip install pybluez
pip install proximity-lock-system
```

Note: On Windows, requirements.txt references pybluez and a 
Windows-friendly pybluez-win10 option. If you have trouble installing 
the library from PyPI, consider installing from the project's GitHub or 
using the pybluez-win10 wheel.

### Setup and start the service

```bash
proximity-lock setup
proximity-lock start
```

### Stop the service
Press `Ctrl + C` to stop the monitoring service.

## Usage

### Running the application

```bash
proximity-lock
```

### Example output
The CLI will scan for nearby Bluetooth devices and prompt you to choose your phone:

```
🔍 Scanning for nearby Bluetooth devices...
Available devices:
[0] Akarsh's iPhone (D8:B0:53:4F:8F:8F)
Enter the number of your phone: 0

📡 Monitoring device: D8:B0:53:4F:8F:8F
✅ Device in range.
✅ Device in range.
⚠️ Device not found (1/2)
⚠️ Device not found (2/2)
🔒 System locked due to phone out of range.
⏸️ Pausing checks for 3 minutes after lock...
```

Once selected, it will monitor the device and lock the system when the phone has been out of range for the configured threshold.

## Platform notes
- Windows: The tool uses `rundll32.exe user32.dll,LockWorkStation` to lock the session. No extra packages are required.
- macOS: Uses `CGSession -suspend`. If that doesn't work on newer macOS versions, consider running an AppleScript or `osascript` command to lock the screen.
- Linux: Calls `gnome-screensaver-command -l` (GNOME). If you use another DE, replace the command with one that works for your environment (for example `loginctl lock-session`, `dm-tool lock`, or other `xdg` alternatives).

## System Performance

### Lock Trigger Latency
![Latency Graph](latency.png)

The graph shows how quickly the system locks the device as the paired device moves away.


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

## Support us by following us on Product Hunt
<p align="center">
  <a href="https://www.producthunt.com/products/proximity-lock-system?launch=proximity-lock-system-2-0" target="_blank">
    <img src="https://raw.githubusercontent.com/Akarshjha03/ProximityLockSystem/main/Images/Screenshot%202025-11-19%20220056.png" width="500" />
  </a>
</p>

## Contributing
PRs welcome. If adding OS support, please include testing notes and required dependencies.

## License
See `PKG-INFO` or project metadata.
