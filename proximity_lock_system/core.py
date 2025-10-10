def monitor_connection(phone_mac, poll_interval, pause_after_unlock):
    print(f"📡 Monitoring {phone_mac} every {poll_interval}s...")
    last_unlock_time = time.time()

    while True:
        # Pause checks after manual unlock
        if time.time() - last_unlock_time < pause_after_unlock:
            time.sleep(poll_interval)
            continue

        if not is_device_in_range(phone_mac):
            print("🔒 Phone out of range — Locking system...")
            lock_system()
            last_unlock_time = time.time()
        else:
            print("✅ Phone in range")

        time.sleep(poll_interval)
