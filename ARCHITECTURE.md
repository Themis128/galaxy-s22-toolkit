# Architecture — Galaxy S22+ Toolkit

**Device**: Samsung Galaxy S22+ (SM-S906B, Exynos 2200, international), serial `RFCTA0AEKZP`
**Platform**: Windows host, ADB at `C:\Users\tbaltzakis\Android\Sdk\platform-tools\adb.exe`
**Python**: ≥ 3.10

## Layer diagram

```
┌──────────────────────────────────────────────────────────────┐
│ dashboard/          FastAPI + WebSocket + Chart.js           │  Layer 4 — observe
│  GET /api/health | GET /api/history | WS /ws/live            │
├──────────────────────────────────────────────────────────────┤
│ .zcode/skills/      5 CLI skills (pip console scripts)       │  Layer 3 — act
│  phone-diagnostics, phone-screen-control,                    │
│  phone-file-transfer, phone-logcat, phone-app-manager        │
├──────────────────────────────────────────────────────────────┤
│ rooting/            phone-root CLI (6th package)             │  Layer 3b — root ops
│  preflight | backup | verify | modules                       │
├──────────────────────────────────────────────────────────────┤
│ diagnostics/        DiagnosticsRunner (scheduled checks)     │  Layer 2 — assess
├──────────────────────────────────────────────────────────────┤
│ phone-lib/          AdbClient + modules + typed models       │  Layer 1 — foundation
│  device, battery, storage, logcat, network, thermal,         │
│  apps, screen, termux, root                                  │
└────────────────────────────────────────────────────────────┘
```

Dependencies point strictly downward. `rooting/` and the skills are thin CLI wrappers
over `phone-lib`; `diagnostics/` uses `phone-lib` for its checks; `dashboard/` uses
`phone-lib` for its collectors.

## Data flow

```
adb.exe (platform-tools)
   ↑ subprocess
AdbClient (phone/adb.py)          serial, retry, timeout, JSON parsing
   ↑ owns lazily
Modules (device/battery/.../root) one per domain, shell/dumpsys parsing
   ↑ return
Dataclasses (phone/models.py)     BatteryInfo, StorageInfo, DeviceInfo,
   ↑ consumed by                   NetworkInfo, ThermalInfo, CpuInfo,
diagnostics / skills / dashboard / MemoryInfo, RootInfo, HealthReport
```

`AdbClient` exposes lazy module properties (`client.battery`, `client.root`, …), so
consumers never construct modules directly.

## Module responsibility table (phone-lib/src/phone/)

| Module | Responsibility | Key entry points |
|---|---|---|
| `adb.py` | Core client: connection, exec, retry, pull/push, lazy modules | `AdbClient`, `create_client()` |
| `device.py` | getprop, model, OS, CPU, memory | `get_device_info`, `get_cpu_info`, `get_memory_info` |
| `battery.py` | dumpsys battery, health, temp, cycles | `get_battery_info`, `get_battery_health` |
| `storage.py` | df, partitions, large files | `get_storage_info`, `get_storage_usage` |
| `logcat.py` | stream/filter logs, crash/ANR detection | `stream()`, `find_crashes`, `find_anrs` |
| `network.py` | Wi-Fi/mobile state, DNS, connectivity | `get_network_info`, `check_dns`, `check_connectivity` |
| `thermal.py` | thermal zones, throttling | `get_thermal_info`, `is_throttling` |
| `apps.py` | packages, permissions, install/uninstall | `list_packages`, `get_app_info`, `get_running_apps` |
| `screen.py` | screencap, screenrecord, UI dump | `screenshot`, `dump_ui` |
| `termux.py` | Termux API bridge (battery/CPU/wifi/boot) | `TermuxClient`, `TermuxBootManager` |
| `root.py` | Privileged ops (guarded) | `is_rooted`, `get_magisk_info`, `run_privileged` |
| `models.py` | Typed dataclasses shared by all layers | — |
| `exceptions.py` | PhoneError hierarchy | — |

## Dashboard API contract

Endpoints: `GET /` (page), `GET /api/health`, `GET /api/history?hours=24`,
`GET /api/history/{metric}` , `WS /ws/live`, `POST /api/diagnostics/run`.

All payload fields come from `phone-lib` models — the authoritative field names:

- **battery**: `level`, `health` (BatteryHealth enum value), `status` (BatteryStatus value),
  `temperature_c/_f`, `voltage_mv`, `technology`, `plugged_type`,
  `current_capacity_mah` (nullable), `charge_cycles` (nullable). There is **no** `current_ma`.
- **storage**: list of partitions: `mount_point`, `total_gb/used_gb/free_gb`, `usage_percent`, `filesystem`.
- **device**: `model`, `android_version`, `api_level`, `security_patch`, `build_number`.
- **network**: `wifi_connected`, `wifi_ssid`, `wifi_signal_dbm`, `wifi_ip`,
  `mobile_connected`, `mobile_type`, `mobile_ip`, `dns_servers`, `gateway`, `internet_reachable`.
  There is **no** `wifi_frequency_mhz` / `mobile_operator` / `mobile_signal_dbm` / `mobile_network_type`.
- **thermal**: `status` (ThermalStatus value), `cpu_throttled`, `gpu_throttled`,
  `zones[]` of `{name, temp_c, type}` — `type` is a plain string (no `.value`, no `is_critical`).
- **cpu**: `cores`, `architecture`, `current_freq_khz[]`, `load_percent[]` (from `get_cpu_info()`).
- **memory**: `total_mb`, `available_mb`, `usage_percent` (from `get_memory_info()`).
- **root**: `rooted`, `magisk_version`, `denylist_enabled`, `knox_status` (from `RootInfo`).

Collector cadence is **5 s** (not 1 s): each snapshot costs several ADB round-trips
(dumpsys battery + df + settings + thermal …); 1 s would flood the ADB server and skew
the very metrics being sampled.

## Rooting safety model

Rooting is supported, never implicit:

1. **The Odin flash is never automated.** `rooting/RUNBOOK.md` documents the manual
   procedure; automation covers everything around it.
2. **Privileged execution is gated.** `RootModule.run_privileged(cmd, confirm=False)`
   raises `PhoneError` unless `confirm=True` is passed explicitly. Pre-root it returns
   a graceful "root unavailable" result instead of failing the caller.
3. **Every mutating CLI op requires `--yes`.** `phone-root backup` (writes), module
   install/disable/remove all demand `--yes` (or `--dry-run`).
4. **Backup-first gate.** `phone-root preflight` refuses GO while `data/backup-<ts>/`
   is missing or older than 24 h.
5. **Knox is permanent.** Bootloader unlock wipes data and trips the Knox eFuse:
   Samsung Pay/Wallet, Secure Folder, Samsung Pass are lost permanently.

## Data directories

| Path | Purpose | Tracked by git |
|---|---|---|
| `data/phone-mirror/` | pulled phone data (DCIM, Pictures, Download, …) | no |
| `data/artifacts/` | screenshots, UI dumps from past sessions | no |
| `data/backup-<ts>/` | pre-flash backups from `phone-root backup` | no |
| `data/reports/` | diagnostics JSON/summary reports | no |
| `storage/` | **legacy OneDrive placeholder dir — do not use** | no |

`storage/` is a legacy folder whose files are OneDrive cloud placeholders
(`RECALL_ON_DATA_ACCESS`); they cannot be moved or read while the cloud provider is
down. `scripts/finish-storage-cleanup.ps1` completes the cleanup (hydrate → move →
verify) when OneDrive is running.

## Config

- `diagnostics/config.yaml` — device serial, thresholds, report paths, false-positive filters.
- Thresholds drive `DiagnosticsRunner` (battery/storage/thermal/network/logcat/apps checks).

## Security posture & accepted risks

Mimosa SAST flagged 4 pre-existing path-traversal findings. Disposition:

| Location | Disposition |
|---|---|
| `diagnostics/run_diagnostics.py:536,547` | **Accepted.** Paths come from the operator's own `config.yaml`; single-user local tool, no untrusted input reaches them. |
| `phone-lib/src/phone/logcat.py:754` | **Accepted.** `save_to_file(file_path)` is an explicit API where the caller chooses the destination; local CLI context. |
| `phone-lib/src/phone/termux.py:256` | **Accepted (blocked from editing).** The intended hardening (`os.path.basename` clamp) could not be applied — the file is held read-only by the security tooling. Risk is bounded: the path targets `~/.termux/boot` on the host only. |

All privileged/mutating paths are gated (see Rooting safety model). The dashboard binds
to all interfaces only when `DASHBOARD_HOST` is set; default `127.0.0.1` is recommended
for local use.

## Extension points

- New metric domain → new module in `phone-lib/src/phone/` + dataclass in `models.py`
  + lazy property in `adb.py` + optional dashboard card.
- New check → method on `DiagnosticsRunner` returning `CheckResult` + entry in
  `run_all_checks()` + threshold in `config.yaml`.
- New CLI capability → new subcommand in the relevant skill's `__init__.py`
  (argparse `set_defaults(func=...)` pattern).
- New root capability → `RootModule` method with `confirm` gate; never call `su` raw.
