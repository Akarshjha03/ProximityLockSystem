import platform
import os

def sleep_system():
    """Put the system to sleep depending on the OS."""
    os_name = platform.system().lower()

    try:
        if "windows" in os_name:
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
        elif "linux" in os_name:
            os.system("systemctl suspend")
        elif "darwin" in os_name:  # macOS
            os.system("pmset sleepnow")
        else:
            print("⚠️ Unsupported OS. Cannot suspend.")
    except Exception as e:
        print(f"❌ Failed to put system to sleep: {e}")
