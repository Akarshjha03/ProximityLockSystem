# Product Requirements: Proximity Lock System

**Document status:** Working requirements baseline  
**Product:** Proximity Lock System  
**Primary target:** macOS CLI and menu bar app (planned)  
**Existing implementation:** Experimental Python CLI under `Platform/Windows`

## 1. Product summary

Proximity Lock System reduces the chance of leaving a computer unlocked when its user walks away. It monitors a user-selected phone using a validated proximity signal and locks the current user session after the phone is confirmed absent for a configured period.

The product must fail safely when it cannot determine proximity. A Bluetooth error, permission denial, adapter failure, or ambiguous scan result must not be treated as proof that the phone is away.

## 2. Goals

- Lock the supported computer after reliable evidence that the configured phone has left range.
- Prevent repeated lock attempts from trapping the user in an unlock/re-lock loop.
- Make monitoring, pause, sensor failure, and re-arm state visible and controllable.
- Provide a documented macOS CLI and a macOS menu bar experience.
- Make platform support and detection limitations explicit.

## 3. Non-goals for the initial macOS release

- Guaranteeing a specific physical distance from Bluetooth signal strength.
- Replacing the operating system's authentication or lock-screen security.
- Locking other user sessions or controlling device-management policy.
- Claiming support for every phone, Bluetooth adapter, macOS version, or desktop environment.

## 4. Users and primary journeys

### First-time setup

The user installs and launches the app, understands why Bluetooth access is requested, grants or declines access, scans for supported devices, selects a phone, tests detection, and explicitly enables monitoring. The app explains how to stop monitoring before the user enables automatic locking.

### Normal monitoring

The app presents a persistent, understandable state: monitoring, phone detected, phone possibly absent, paused, or sensor unavailable. When reliable absence reaches the configured threshold, it attempts a session lock and records the result.

### Recovery after locking

After a lock attempt the system enters `DISARMED_AFTER_LOCK`. It does not issue another automatic lock. After the user unlocks, the app allows the configured cooldown. Re-arming requires a deliberate user action and a positive detection scan. If Bluetooth cannot verify the phone, the app remains disarmed and explains the recovery path.

### Sensor failure

When scanning fails, the app reports the reason where available, does not increment the absence count, and does not lock based on that result. It must show that proximity protection is degraded so the user can address it.

## 5. Safety behavior and state model

| State | Meaning | Lock behavior |
| --- | --- | --- |
| `UNCONFIGURED` | No target phone selected | No monitoring or locking |
| `ARMED` | Sensor is available and monitoring is enabled | May lock after the absence threshold |
| `PHONE_PRESENT` | Most recent valid observation detected the target | Reset absence streak |
| `ABSENCE_PENDING` | One or more valid scans missed the target, below threshold | Continue checks; do not lock yet |
| `SENSOR_UNAVAILABLE` | Permission, adapter, scanner, or runtime error prevents a valid observation | Do not count a miss or lock |
| `LOCKING` | A threshold was met and a lock command is being attempted | Record the outcome |
| `DISARMED_AFTER_LOCK` | Lock attempt completed or failed | Never retry automatically; wait for cooldown and explicit re-arm |
| `STOPPED` | Monitoring is disabled | No monitoring or locking |

An invalid or failed scan is **unknown**, not absent. Only valid observations from the selected sensing method may contribute to the absence threshold. A lock attempt, whether successful or not, must leave the monitor disarmed. Re-arm must require a deliberate user action and positive phone detection. This makes the first release safer even if it requires user intervention after every lock.

### Lock-loop prevention requirement

The app must never repeatedly lock after each unlock because the phone is nearby but not visible to its scanner. Following a lock attempt, automatic locking remains disabled until re-arm succeeds. Re-arm is rejected if the cooldown is active, the scanner fails, or the phone is not positively detected. The CLI implementation exposes this as `resume`; the future menu bar app must provide an equivalent visible action.

## 6. Functional requirements

### Monitoring and lock

- The user can select and change a target phone.
- The user can start, pause, resume, and stop monitoring.
- The user can configure polling cadence, absence threshold, scan duration, and post-lock cooldown within validated bounds.
- The app distinguishes a valid scan with no target from scan failure or unavailable permission.
- The app records lock command success or failure and exposes the result.
- The app does not unlock the computer or weaken system authentication.
- The app preserves a reliable stop/recovery path after a lock.

### macOS menu bar app

- The menu bar item communicates monitoring state without requiring an open terminal.
- The menu includes setup/device selection, start/stop, re-arm, settings, help, and quit.
- Bluetooth permission denial and launch-at-login status have actionable guidance.
- Launch at login is opt-in and uses supported macOS service-management mechanisms for the declared minimum OS version.
- The app provides a user-facing reason when monitoring is disarmed or degraded.

### CLI

- Commands support non-interactive operation for setup, status, start, stop, and diagnostics.
- Interactive prompts are optional and do not block background service operation.
- Exit codes distinguish success, invalid configuration, unavailable Bluetooth, and lock failure.
- CLI and menu bar app share configuration and monitoring state through a documented service boundary.

## 7. Reliability, privacy, and security

- No cloud account or network service is required for proximity monitoring.
- Persist only settings needed to operate; document where they are stored and how to remove them.
- Store the phone identifier and display name as local configuration; do not transmit them.
- Request Bluetooth access only through the app identity that needs it and explain the purpose.
- Keep lock execution limited to the current logged-in user's session and use platform APIs or verified commands.
- Never silently equate a scan error with absence.
- Treat unsupported OS versions, phone behavior, and desktop environments as unsupported until verified.
- Provide logs that are useful for diagnosis without unnecessarily exposing device identifiers.

## 8. Platform support policy

| Platform | Status | Release gate |
| --- | --- | --- |
| Windows CLI | Experimental existing implementation | Safety-state behavior and real hardware recovery validation |
| macOS CLI | Planned | Supported phone detection, permissions, lock behavior, packaging, and recovery verified |
| macOS menu bar app | Planned; primary product direction | Full setup, status, stop/re-arm, login behavior, signing/distribution, and accessibility review |
| Linux | Unvalidated | Per-desktop lock behavior and package validation |

The project must not advertise a platform as supported based only on a code branch or a documented command. A support claim requires validation on named OS versions and hardware combinations.

## 9. Acceptance criteria for the next release

### Safety hotfix

1. After any lock attempt, no second automatic lock occurs until a deliberate re-arm action succeeds.
2. Re-arm fails while the cooldown is active.
3. Re-arm requires a successful scan that positively detects the selected phone.
4. Scanner errors do not increment the miss count and are visible to the user.
5. Lock command failures are visible and still leave monitoring disarmed.
6. Status distinguishes monitor process state from whether automatic locking is armed.

### macOS MVP

1. A first-time user can install, grant Bluetooth access, select a supported phone, and enable monitoring without editing source files.
2. The app provides an explicit, tested stop/recovery route from both menu bar and CLI.
3. Phone detection is validated with screen locked, phone locked, phone connected, sleep/wake, and Bluetooth permission changes.
4. Lock and re-arm behavior is verified for each declared macOS release and supported phone model.
5. Installation and update instructions cover signing, distribution, launch at login, uninstall, and permission reset.
6. All unsupported or degraded states explain what is happening and how to recover.

## 10. Open decisions

- Which macOS and Windows versions are supported at launch?
- Which phone models and OS versions must be supported?
- Which proximity signal can reliably distinguish “nearby” from “away” for those phones?
- Should re-arm remain manual after every lock, or may it become automatic after an OS unlock event and confirmed sensor recovery?
- What distribution channel will be used, and what signing/notarization requirements follow?
- What diagnostics may be retained locally, and for how long?

These decisions must be resolved through hardware and platform validation, not assumed from the current classic Bluetooth inquiry implementation.
