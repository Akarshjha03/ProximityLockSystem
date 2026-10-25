# Architecture and Developer Guide

## 1. Scope and current state

This document describes the code that exists today. The package is a Python CLI in `Platform/Windows`; it is not yet a cross-platform application. `Platform/Mac` and `Platform/Linux` contain placeholders. The shared Python core contains branches for Windows, macOS, and Linux lock commands, but those branches have not been validated as supported products.

Product requirements, safety guarantees, and release gates are defined in [PRD.md](PRD.md). The user-facing overview and CLI instructions are in [README.md](README.md).

## 2. Repository map

```text
assets/                                      Branding and screenshots
Platform/Windows/
  proximity_lock_system/
    cli.py                                   Interactive CLI and command dispatch
    config.py                                JSON configuration persistence
    core.py                                  Monitor thread and lock command dispatch
    utils.py                                 Bluetooth discovery wrapper
    __init__.py                              Package version
  setup.py                                   Package metadata and console entry point
  requirements.txt                           Development dependency notes
Platform/Mac/                                Placeholder; no macOS app target
Platform/Linux/                              Placeholder; no Linux package
PRD.md                                       Product requirements and release criteria
README.md                                    Install, use, support status
ARCHITECTURE.md                              This guide
```

Generated `build`, `dist`, `*.egg-info`, and `__pycache__` directories are build artifacts, not source of truth.

## 3. Current runtime flow

1. `cli.py` loads settings and prompts for a command.
2. `scan` uses `utils.discover_nearby_devices()` and stores results in process memory.
3. `set-device <number>` stores the selected address and name through `config.py`.
4. `start` starts `MonitorThread` with the saved target and timing settings.
5. `core.is_device_in_range()` checks the discovery result. It returns `True` when the target is found, `False` when a scan completes without it, and `None` when scanning fails.
6. Only valid absence results increment the consecutive miss count. Reaching the threshold invokes `lock_system()`.
7. After every lock attempt, the monitor clears its armed event. It remains disarmed until cooldown has elapsed and the CLI `resume` command performs a successful scan that detects the target.

## 4. Safety state and recovery

The safety latch addresses the re-lock loop: after a lock attempt, the monitor cannot issue another automatic lock. This applies whether the lock command reports success or failure. `resume` refuses when the monitor is stopped, already armed, within cooldown, when Bluetooth scanning fails, or when the target is not detected.

Bluetooth errors are unknown observations. `utils.py` raises `BluetoothScanError` for scanner failures, and the monitor resets the current miss streak rather than incrementing it. The CLI reports errors during a manual scan. If the Bluetooth dependency is missing, the module remains importable and reports that the scan cannot run.

This initial recovery policy is intentionally manual. It prioritizes avoiding repeated locks over seamless automatic recovery. A future menu bar app must expose the same disarmed state and re-arm decision. Automatic re-arm should only be considered after OS unlock detection and phone detection have been validated on supported hardware.

## 5. Module responsibilities

### `config.py`

Loads and saves a JSON object at `~/.proximity_lock_config.json`, merging persisted values with defaults. Current defaults are defined in `DEFAULTS`. There is no schema versioning or validation beyond conversions performed by `MonitorThread`; this should be improved before settings become shared between a CLI and GUI.

### `utils.py`

Wraps PyBluez classic Bluetooth discovery and normalizes results into `(address, name)` tuples. Scanner failures raise `BluetoothScanError`; an empty successful result is distinct from an error. The current sensing method is not proven to detect all phones while connected, locked, or non-discoverable and must not be presented as a reliable distance measurement.

### `core.py`

`lock_system()` dispatches a platform lock command and returns a boolean based on process completion/return code. `MonitorThread` owns the polling loop, absence threshold, stop event, and post-lock armed event. It prints status messages to stdout. It does not currently provide a structured event API, persistent service process, OS unlock notification, or GUI integration.

Lock command return codes are only an initial signal; they do not prove that the active user session is locked. The platform branches require validation and stronger APIs/error handling before any support claim.

### `cli.py`

Implements an interactive REPL, device selection, monitor lifecycle, `status`, and the post-lock `resume` action. The monitor state is process-local. The CLI has no argument parser, daemon/service mode, interprocess control, or structured exit-code contract yet.

## 6. Current configuration

| Key | Default | Description |
| --- | ---: | --- |
| `PHONE_MAC` | `null` | Selected target address |
| `DEVICE_NAME` | `null` | Human-readable target name |
| `POLL_INTERVAL` | `10` | Seconds between checks |
| `UNLOCK_PAUSE` | `180` | Minimum seconds after a lock attempt before re-arm |
| `SAFETY_THRESHOLD` | `2` | Valid consecutive scans that miss the phone |
| `SCAN_DURATION` | `5` | Bluetooth inquiry duration in seconds |

The setting name `UNLOCK_PAUSE` is historical; it is a cooldown after a lock attempt. Renaming it requires migration for existing config files.

## 7. Known technical gaps

- The package and dependency metadata are Windows-oriented and not separated by platform.
- The classic Bluetooth inquiry and address matching strategy has not been validated for modern iPhones or reliable background proximity detection.
- The lock command branches are shell/process based, and successful process return does not prove session lock state.
- `MonitorThread` prints directly to stdout and is coupled to the CLI rather than a service/event interface.
- Configuration has no schema version, validation, or platform-specific app data location.
- There is no background service lifecycle, menu bar UI, launch-at-login flow, signed app bundle, updater, or uninstall flow.
- No automated test suite or hardware validation matrix is present in this repository.

## 8. macOS target architecture

The intended design is a user-facing menu bar app and CLI over a shared monitoring service boundary. Before implementation, choose and validate a phone-proximity API and define permission behavior. Keep the macOS app responsible for permission requests and visible status; use a supported login item or agent mechanism for launch-at-login where applicable. Apple documents protected-resource usage descriptions and `SMAppService` for login items and agents ([protected resources](https://developer.apple.com/documentation/bundleresources/protected-resources), [`SMAppService`](https://developer.apple.com/documentation/servicemanagement/smappservice)).

The service boundary should provide typed observations (`present`, `absent`, `unavailable`), explicit monitor states, lock attempt results, and user-controlled re-arm. A GUI should not need to inspect thread internals or parse terminal output.

## 9. Development notes

From a Windows development environment:

```powershell
cd Platform/Windows
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
proximity-lock
```

The current package requires a compatible PyBluez dependency. Building or running on macOS requires a separate, validated implementation and should not be inferred from the presence of the `Darwin` branch in `core.py`.

## 10. Change requirements

Changes to monitoring or locking must document the effect on the safety state machine, user recovery path, and failure behavior. Platform support changes must name tested OS versions, phone models, adapters, scan results, and lock outcomes. Do not describe a platform as supported until those checks have been completed and reflected in the PRD and README.
