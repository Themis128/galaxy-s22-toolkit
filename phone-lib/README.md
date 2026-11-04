# Galaxy S22+ Phone Toolkit

A comprehensive Python ADB wrapper library for Samsung Galaxy S22+ (SM-S906B) diagnostics, monitoring, and management.

## Features

- **Typed ADB Client** - Async/sync execution with retry logic and exponential backoff
- **Device Information** - Model, Android version, security patch, build fingerprint, CPU, memory
- **Battery Monitoring** - Level, health, temperature, voltage, charge cycles, charging status
- **Storage Analysis** - Partition usage, large file finder, app storage breakdown
- **Logcat Streaming** - Real-time filtering, crash/ANR detection, permission denial tracking
- **Network Diagnostics** - Wi-Fi/mobile status, DNS, gateway, internet connectivity, speed tests
- **Thermal Monitoring** - Zone temperatures, throttling detection, CPU/GPU thermal status
- **App Management** - List/install/uninstall, permissions, cache/data clearing, freeze/thaw
- **Screen Control** - Screenshots, screen recording, UI dumps, input simulation

## Installation

```bash
pip install -e ./phone-lib
```

Or with development dependencies:

```bash
pip install -e ./phone-lib[dev]
```

## Quick Start

```python
from phone import create_client, DeviceModule, BatteryModule, StorageModule

# Create client (auto-detects Galaxy S22+ serial RFCTA0AEKZP)
client = create_client()

# Get device info
device = DeviceModule(client)
info = device.get_device_info()
print(f"{info.model} - Android {info.android_version} - Patch: {info.security_patch}")

# Get battery info
battery = BatteryModule(client)
bat = battery.get_battery_info()
print(f"Battery: {bat.level}% ({bat.health.value}) - {bat.temperature_c:.1f}°C")

# Get storage info
storage = StorageModule(client)
for part in storage.get_storage_info():
    print(f"{part.mount_point}: {part.usage_percent:.1f}% used ({part.free_gb:.1f}GB free)")

# Stream logcat for crashes
logcat = LogcatModule(client)


def on_crash(entry):
    print(f"CRASH: {entry.tag}: {entry.message}")


logcat.monitor_for_crashes(on_crash, package_name="com.example.app")
```

## Async Usage

```python
import asyncio
from phone import create_client


async def main():
    client = create_client()

    # Async shell command
    output = await client.shell_async("dumpsys battery")
    print(output)

    # Async execute
    result = await client.execute_async("getprop", "ro.build.version.release")
    print(f"Android: {result}")


asyncio.run(main())
```

## Modules

| Module | Class | Description |
|--------|-------|-------------|
| `adb` | `AdbClient` | Core ADB connection and command execution |
| `device` | `DeviceModule` | Device properties, CPU, memory info |
| `battery` | `BatteryModule` | Battery health, temperature, charge cycles |
| `storage` | `StorageModule` | Partition usage, large files, app storage |
| `logcat` | `LogcatModule` | Log streaming, crash/ANR detection |
| `network` | `NetworkModule` | Wi-Fi, mobile, DNS, connectivity |
| `thermal` | `ThermalModule` | Thermal zones, throttling status |
| `apps` | `AppsModule` | Package management, permissions |
| `screen` | `ScreenModule` | Screenshots, recording, UI dumps |
| `repair` | `RepairModule` | Approved repair actions with persistent JSONL history |
| `notify` | `DesktopNotifier` | Windows toast notifications with Approve/Deny buttons |
| `paths` | `confined_path` | Path confinement (resolve + fixed-root verification) |

## Repair Actions

`phone.repair.RepairModule` provides ~20 audited repair actions (storage,
apps, network, logcat). Approval policy: actions flagged `auto_approve` or
matching the configured `auto_approve_risk_levels` run without prompting;
everything else requires an explicit approval (toast buttons or callback).
Every executed result is appended to a JSONL history file and reloaded on
the next run.

```python
from phone.repair import RepairModule

repair = RepairModule(client, history_path="logs/repair_history.jsonl")
results = await repair.execute_multiple(["clear_app_caches", "flush_dns"])
```

Actions that need root (e.g. tombstone/ANR cleanup) are flagged
`requires_root=True` and report an honest failure on unrooted devices
instead of a silent no-op. Network toggles always attempt re-enable so a
half-failed reset never leaves a radio off.

## Desktop Notifications

```python
from phone.notify import DesktopNotifier

notifier = DesktopNotifier(app_id="Galaxy S22+ Toolkit", dashboard_url="http://127.0.0.1:8081")
notifier.notify("Health check", "All checks passed")
approved = await notifier.request_approval_async(
    "Repair: reset_wifi", "Toggles Wi-Fi off/on", timeout_s=120
)
```

Requires the optional `notify` extra (`pip install galaxy-s22-toolkit[notify]`,
Windows only). Timeout counts as denial.

## Path Confinement

```python
from phone.paths import confined_path, PathEscapeError

target = confined_path(root_dir, user_supplied)  # raises PathEscapeError
```

Every file write in the library resolves its candidate against a fixed
root and rejects `..` segments outright.

## Data Models

All modules return typed dataclasses with slots for performance:

```python
from phone.models import BatteryInfo, StorageInfo, DeviceInfo, HealthReport

# Full health report
report = HealthReport(
    device=device_info,
    battery=battery_info,
    storage=storage_list,
    network=network_info,
    thermal=thermal_info,
)
print(report.summary)
print(report.is_healthy)
```

## Requirements

- Python 3.10+
- Android SDK Platform Tools (adb in PATH or at default locations)
- Samsung Galaxy S22+ with USB debugging enabled
- Device authorized (RSA key accepted on phone)

## ADB Path Detection

The client automatically searches for ADB at:
1. `C:\Users\tbaltzakis\Android\Sdk\platform-tools\adb.exe` (Windows)
2. `/mnt/c/Users/tbaltzakis/Android/Sdk/platform-tools/adb` (WSL)
3. `~/Android/Sdk/platform-tools/adb` (Linux/macOS)
4. `/c/Users/tbaltzakis/Android/Sdk/platform-tools/adb` (Git Bash)
5. `adb` (system PATH)

## Testing

```bash
# Run unit tests (mocked ADB)
pytest tests/

# Run integration tests (requires physical device)
pytest tests/ -m device

# Run with coverage
pytest --cov=phone tests/
```

## Code Quality

```bash
# Lint
ruff check .

# Format
ruff format .

# Type check
mypy src/phone
```

## License

MIT License