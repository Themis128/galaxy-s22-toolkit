# Architecture — Galaxy S22+ Toolkit

**Device**: Samsung Galaxy S22+ (SM-S906B, Exynos 2200, international), serial `RFCTA0AEKZP`
**Canonical repo**: `C:\dev\galaxy-s22-toolkit` (git `master`)
**Platform**: Windows host on a Tailscale tailnet (`100.83.120.93`); phone on the same tailnet (`100.84.31.85`), wireless ADB on TCP 5555
**Python**: ≥ 3.10

The toolkit is a single-user, single-active-device suite: it adapts to whatever Galaxy is attached (multi-Galaxy compatibility layer, below), keeps all privileged operations behind explicit gates, and degrades to honest "N/A" rather than lying or crashing.

## Deployment topology

```
                    Tailscale tailnet
  ┌───────────────────────────────────────────────────────────────┐
  │                                                               │
  │   Phone (galaxy-s22)                Windows host (office-1)   │
  │   100.84.31.85                      100.83.120.93             │
  │   SM-S906B Android 16               ├─ Docker: dashboard      │
  │   adb listen_tcp:5555  ←── ADB ──→  │    (network_mode: host) │
  │                                     │    :8081                │
  │                                     ├─ adb.exe (host server)  │
  │                                     ├─ nightly schtasks       │
  │                                     │    03:00 diag           │
  │                                     │    03:30 backup         │
  │                                     │    03:45 rollup         │
  │                                     └─ ZCode / Groq bot       │
  │                                        (X-API-Key client)     │
  └───────────────────────────────────────────────────────────────┘
```

- The dashboard container runs with `network_mode: host`, so it shares the host's
  tailnet interface and reaches the phone directly at `100.84.31.85:5555`
  (compose sets `PHONE_ADB_HOST`, `adb connect` runs at container start).
- Any browser on the tailnet (phone, other machines, ZCode's integrated browser)
  can open `http://100.83.120.93:8081/`. CORS is allow-all so cross-origin
  clients work; the sensitive `/api/devin/*` endpoints still require `X-API-Key`
  and an optional IP allowlist (`TAILSCALE_ALLOWLIST`).
- The nightly pipeline runs from the canonical tree via registered schtasks
  (diagnostics 03:00, metrics backup 03:30, rollup 03:45).

## Layer diagram

```
┌────────────────────────────────────────────────────────────────┐
│ dashboard/       FastAPI + WebSocket + Chart.js + SQLite       │  Layer 4 — observe
│  /api/health | /api/history | /api/trends/* | /api/alerts      │
│  /api/repair/* | /api/root* | /api/insights | /api/devin/*     │
│  WS /ws/live (5 s broadcasts)                                  │
├────────────────────────────────────────────────────────────────┤
│ .zcode/skills/   20 CLI skills (pip console scripts)           │  Layer 3 — act
│  phone-diagnostics, phone-repair, phone-insights,              │
│  phone-connect, phone-screen-control, phone-file-transfer,     │
│  phone-logcat, phone-app-manager, phone-update-check,          │
│  phone-doctor, phone-relocate, phone-remote-control            │
├────────────────────────────────────────────────────────────────┤
│ rooting/         phone-root CLI (13th package)                 │  Layer 3b — root ops
│  preflight | backup | verify | modules                          │
├────────────────────────────────────────────────────────────────┤
│ diagnostics/     DiagnosticsRunner (scheduled + on-demand)     │  Layer 2 — assess
├────────────────────────────────────────────────────────────────┤
│ tools/           13 standalone utilities (doctor, insights,    │  Layer 2b — operate
│                  alerts, backup/restore, dashboard_client, …)   │
├────────────────────────────────────────────────────────────────┤
│ phone-lib/       AdbClient + 16 modules + typed models         │  Layer 1 — foundation
│  device, battery, storage, logcat, network, thermal,           │
│  apps, screen, termux, root, repair, notify, paths,            │
│  capabilities, models                                          │
└────────────────────────────────────────────────────────────────┘
```

Dependencies point strictly downward. `rooting/` and the skills are thin CLI wrappers over `phone-lib`; `diagnostics/` uses `phone-lib` for its checks; `dashboard/` uses `phone-lib` for its collectors, repair layer and root module; `tools/` are standalone (the only one that talks to the dashboard is `dashboard_client.py`).

## Full Mobile Suite (v0.6.0 — Wondershare-class pillars, all open source)

External pillars and their toolkit entry points: **scrcpy 5** (`tools/mirror.py`,
skill `phone-mirror` — mirror/record/control, no root) · **libimobiledevice**
(`phone-lib/imobile.py`, skill `phone-ios` — iTunes-free iOS backup/info/
screenshot/apps) · **wa-crypt-tools** (Tier B WhatsApp backup decryption,
root-gated, skill `phone-recover`) · **Heimdall** (`tools/repair_system.py`,
skill `phone-repair-system` — Samsung stock-firmware wizard, triple-gated) ·
WhatsApp's **official QR chat transfer** (`tools/whatsapp_transfer.py`, skill
`phone-whatsapp`). Device **verification report** (`phone-verify`) and the
dashboard **Device Files manager** (`/api/device/files*`) formalize the
Phone-Manager/Verification pillars. Anti-theft bypasses (FRP/lock/iCloud/SIM)
are excluded by design. External-binary discovery uses `tools/binfind.py`
(winget Links/package fallback for stale PATHs).

## Data flow

```
adb.exe (platform-tools)
   ↑ subprocess (or TCP to 100.84.31.85:5555 when wireless)
AdbClient (phone/adb.py)          serial, retry, timeout, JSON parsing
   ↑ owns lazily
Modules (device/battery/.../root)  one per domain, shell/dumpsys parsing
   ↑ return
Dataclasses (phone/models.py)      DeviceInfo, BatteryInfo, StorageInfo,
   ↑ consumed by                   NetworkInfo, ThermalInfo, CpuInfo,
diagnostics / skills / dashboard   MemoryInfo, RootInfo, HealthReport
```

`AdbClient` exposes lazy module properties (`client.battery`, `client.root`, …), so consumers never construct modules directly. `create_client()` handles serial resolution and wireless-ADB auto-reconnect (`diagnostics/config.yaml` → `device.wireless_adb`).

## Module responsibility table (phone-lib/src/phone/)

| Module | Responsibility | Key entry points |
|---|---|---|
| `adb.py` | Core client: connection, exec, retry, pull/push, lazy modules | `AdbClient`, `create_client()` |
| `device.py` | getprop, model, OS, CPU, memory | `get_device_info`, `get_cpu_info`, `get_memory_info` |
| `battery.py` | dumpsys battery, health, temp, cycles, **current** | `get_battery_info`, `get_battery_health` |
| `storage.py` | df, partitions, large files | `get_storage_info`, `get_storage_usage` |
| `logcat.py` | stream/filter logs, crash/ANR detection | `stream()`, `find_crashes`, `find_anrs` |
| `network.py` | Wi-Fi/mobile state, DNS, connectivity | `get_network_info`, `check_dns`, `check_connectivity` |
| `thermal.py` | thermal zones, throttling | `get_thermal_info`, `is_throttling` |
| `apps.py` | packages, permissions, install/uninstall | `list_packages`, `get_app_info`, `get_running_apps` |
| `screen.py` | screencap, screenrecord, UI dump | `screenshot`, `dump_ui` |
| `termux.py` | Termux API bridge (battery/CPU/wifi/boot) | `TermuxClient`, `TermuxBootManager` |
| `root.py` | Privileged ops (confirm-gated) + Magisk module state | `is_rooted`, `get_root_info`, `run_privileged(confirm=True)`, `list_modules`, `set_module_state` |
| `repair.py` | ~20 audited repair actions, approval policy, JSONL history | `get_pending_actions`, `execute_action`, `execute_multiple` |
| `notify.py` | Windows toasts with Approve/Deny approval buttons | `DesktopNotifier.notify`, `request_approval_async` |
| `capabilities.py` | Multi-Galaxy DeviceProfile detection (see below) | `detect_profile`, `describe_model` |
| `paths.py` | Path confinement (resolve + fixed-root verification) | `confined_path` |
| `imobile.py` | iOS devices via libimobiledevice (info/backup/restore/screenshot/apps) | `IMobileClient`, `parse_ideviceinfo` |
| `models.py` | Typed dataclasses shared by all layers | — |
| `exceptions.py` | PhoneError hierarchy | — |

## Dashboard API contract

Base URL on this deployment: `http://100.83.120.93:8081` (host-network container). All payload fields come from `phone-lib` models — the authoritative field names. `GET /api/health` triggers a fresh collection; the WebSocket (`/ws/live`) delivers the same shape every 5 s (`initial` then `metrics` messages).

### Snapshot sections (`/api/health`, `/ws/live`)

- **device**: `model`, `android_version`, `api_level`, `security_patch`.
- **device_profile**: `model`, `marketing_name`, `series` (S/Note/A/other/unknown), `year_class`, `chipset`, `api_level`, `one_ui`, `is_samsung`, `flags[]` (`android_10_plus`, `android_13_plus`).
- **battery**: `level`, `health`, `status`, `temperature_c/_f`, `voltage_mv`, `technology`, `plugged_type`, `current_capacity_mah`, `charge_cycles`, **`current_ma`** (nullable — dumpsys `current now` → sysfs `current_now` fallback with µA-vs-mA magnitude check), `charge_counter_uah` (nullable).
- **storage**: list of partitions: `mount_point`, `total_gb/used_gb/free_gb`, `usage_percent`, `filesystem`.
- **network**: `wifi_connected`, `wifi_ssid`, `wifi_signal_dbm`, `wifi_ip`, `mobile_connected`, `mobile_type`, `mobile_ip`, `dns_servers`, `gateway`, `internet_reachable`.
- **thermal**: `status`, `cpu_throttled`, `gpu_throttled`, `zones[]` of `{name, temp_c, type}`.
- **cpu**: `count`, `per_core_mhz[]` (cpufreq sysfs fallback when /proc/cpuinfo lacks frequencies).
- **memory**: `total_mb`, `available_mb`, `usage_percent`.
- **apps**: `running_count`, `running` (first 10).
- **root**: `rooted`, `su_path` (nullable), `magisk_version` (nullable), `denylist_enabled`, `modules_dir_present`, `knox_status` (`unknown | intact | tripped`).

### Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /` | Dashboard page (Jinja2 + Chart.js) |
| `GET /alerts` | Human-readable alert board (auto-refresh, severity-sorted) |
| `GET /api/health` | Fresh snapshot (503 when the device is unreachable) |
| `GET /api/history?hours=24` | In-memory ring buffer time-series |
| `GET /api/history/{metric}` | Time-series of one section (e.g. `battery`) |
| `GET /api/trends/metrics` | Metric paths with persisted data in the window |
| `GET /api/trends/hourly/{metric_path}` / `daily/{metric_path}` / `stats/{metric_path}` | Hourly/daily rollups and min/max/avg from SQLite |
| `POST /api/trends/rollup` | Manually trigger rollup computation |
| `GET /api/alerts` | Severity-sorted alerts (insights + thresholds) |
| `GET /api/insights` | Degradation insights from raw history (drain rate, storage ETA, p95s) |
| `GET /api/repair/actions` | Recommended actions from the latest saved diagnostics report |
| `POST /api/repair/execute` | Run one repair action; non-auto actions need `{"confirm": true}` else **202 confirmation_required** |
| `POST /api/repair/execute-multiple` | Same gate for any non-auto action in the batch |
| `GET /api/repair/history` | Persistent repair history (JSONL) |
| `GET /api/root` | Full root/Magisk state (root card source of truth) |
| `GET /api/root/modules` | Magisk module list (`{id, disabled, pending_removal}`) |
| `POST /api/root/modules/{id}/{action}` | enable/disable/remove — **confirm-gated**, marker-file semantics, effective at next boot |
| `POST /api/diagnostics/run` | Trigger a full diagnostics run (~13 s) |
| `WS /ws/live` | Live updates: `initial` snapshot then `metrics` broadcasts every 5 s |

### Devin control API (API-key protected)

`/api/devin/*` requires the `X-API-Key` header (env `GROQ_BOT_API_KEY`; optional `TAILSCALE_ALLOWLIST` IP gate). All paths confined to the Devin workdir.

| Endpoint | Purpose |
|---|---|
| `GET /api/devin/status` | Devin process + workdir status |
| `POST /api/devin/execute` | Run a shell command in the workdir |
| `GET /api/devin/files?path=.` | List workdir entries |
| `GET /api/devin/files/read?path=x` | Read a file (≤ 1 MB) |
| `POST /api/devin/files/write` | Write a file |
| `DELETE /api/devin/files?path=x` | Delete a file |
| `GET /api/devin/logs` | Tail the newest workdir log |

## Multi-Galaxy compatibility layer

The toolkit adapts to any Samsung Galaxy S/Note/A phone on Android 10+ (the S22+ is the newest anchor; older models degrade to honest "N/A" instead of errors).

- **`phone.capabilities`** — probe-first `DeviceProfile`: `detect_profile()` reads
  getprop directly; marketing names resolve from a model-core map
  (`SM-S906B → "S22+"`, S8–S24, Note8–20, common A cores) with a rule-based
  A-series fallback (`SM-A546B → A54`); chipset decodes from
  `ro.board.platform`/`ro.soc.model`/`ro.hardware` (Exynos/Qualcomm table +
  regex fallbacks); One UI decodes from `ro.build.version.oneui` (80000 → 8.0).
  Unknown models keep raw codes — no guessing.
- **Battery current** — `dumpsys battery` "current now" line, then sysfs
  `/sys/class/power_supply/battery/current_now` with a µA-vs-mA magnitude
  sanity check; implausible values stay `None` (honest N/A).
- **Bloatware repair** — one `pm list packages` pass partitions targets into
  installed/disabled/absent; absent packages are reported, not attempted, so
  the same action list works on models that never shipped the bloat.
- **Branding** — reports, toasts, and the alert board derive "Galaxy S22+
  (SM-S906B)" from the detected profile (`describe_model`); fallback "Galaxy".

## Rooting safety model

Rooting is supported, never implicit:

1. **The Odin flash is never automated.** `rooting/RUNBOOK.md` documents the manual procedure; automation covers everything around it.
2. **Privileged execution is gated twice.** `RootModule.run_privileged(cmd, confirm=False)` raises `PhoneError` unless `confirm=True`. The dashboard module API adds its own gate: `POST /api/root/modules/{id}/{action}` returns **202 confirmation_required** unless the body carries `"confirm": true`; module ids must match `^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$` (keeps shell metacharacters and `..` out of the su command line).
3. **Every mutating CLI op requires `--yes`** (or `--dry-run`) on the `phone-root` CLI.
4. **Backup-first gate.** `phone-root preflight` refuses GO while `data/backup-<ts>/` is missing or older than 24 h.
5. **Module changes are marker files.** enable/disable/remove touch/remove marker files under `/data/adb/modules/<id>/`; Magisk applies them at next boot — nothing runs immediately.
6. **Knox is permanent.** Bootloader unlock wipes data and trips the Knox eFuse (Samsung Pay/Wallet, Secure Folder, Samsung Pass are lost permanently). `knox_status` in the root card tells you where you stand.

## Data directories

| Path | Purpose | Tracked by git |
|---|---|---|
| `data/phone-mirror/` | pulled phone data (DCIM, Pictures, Download, …) | no |
| `data/artifacts/` | screenshots, UI dumps from past sessions | no |
| `data/backup-<ts>/` | pre-flash backups from `phone-root backup` | no |
| `data/reports/` + `diagnostics/reports/` | diagnostics JSON/summary reports | no |
| `logs/` | diagnostics log, repair_history.jsonl | no |
| `backups/` | metrics DB backups (from `tools/backup_metrics_db.py`) | no |
| `dashboard/data/` | live SQLite metrics (named Docker volume in deployment) | no |

The legacy OneDrive placeholder directory `storage/` was decommissioned (`tools/decommission_legacy.py`); `scripts/finish-storage-cleanup.ps1` remains only as a record of the cleanup procedure.

## Config

- `diagnostics/config.yaml` — device serial (optional — auto-detect picks the only attached phone), wireless ADB settings (phone tailnet IP + port 5555 + auto-reconnect), thresholds (battery/storage/thermal/network/logcat/security), repair approval policy (`auto_approve_risk_levels`, `approval_timeout_s`), notification toggles, report paths.
- `docker-compose.yml` — host networking, ADB key mounts, `PHONE_ADB_HOST`, named `metrics-data` volume.
- Thresholds drive `DiagnosticsRunner` (battery/storage/thermal/network/logcat/apps checks).

## Security posture & accepted risks

- **CORS is allow-all** so the ZCode integrated browser and other cross-origin tailnet clients work. Accepted risk: this is a single-user tailnet service; the sensitive endpoints (`/api/devin/*`) are API-key + optionally IP-allowlist protected, and every mutating endpoint (repairs, module changes) carries its own confirm gate.
- **SSRF validation** in `tools/dashboard_client.py` re-validates the blocklist on **every** request (validate-once/DNS-rebinding window closed in 0.4.0); Tailscale CGNAT (100.64.0.0/10) is allowed.
- **Path traversal dispositions** (Mimosa SAST): `diagnostics/run_diagnostics.py:536,547` **accepted** (paths come from the operator's own config.yaml); `phone-lib/.../logcat.py:754` **accepted** (explicit API, caller-chosen destination); `phone-lib/.../termux.py:256` **accepted (blocked from editing)** — bounded: host-only `~/.termux/boot` target.
- **Devin file API** is confined to `DEVIN_WORKDIR` with resolve+relative_to checks on every path; file size capped at 1 MB.
- **Dashboard binding**: default `127.0.0.1`; the container sets `DASHBOARD_HOST=0.0.0.0` (host-network mode makes it reachable from the tailnet — intentional, see topology).
- **All privileged/mutating paths are gated** (rooting safety model above); repair and module APIs return 202 confirmation_required until `confirm: true` is sent.

## Extension points

- **New metric domain** → module in `phone-lib/src/phone/` + dataclass in `models.py` + lazy property in `adb.py` + snapshot section in `dashboard/app.py::_collect_once` + optional dashboard card.
- **New check** → method on `DiagnosticsRunner` returning `CheckResult` + entry in `run_all_checks()` + threshold in `config.yaml`.
- **New API endpoint** → route in `dashboard/app.py`; degrades to 503 when the device is unreachable; mutating endpoints follow the confirm-gate pattern (202 unless `"confirm": true`).
- **New root capability** → `RootModule` method with `confirm` gate; never call `su` raw.
- **New device model** → add the model core to `_MODEL_CORES` in `capabilities.py` (or rely on the A-series rule); unknown models already work via conservative defaults.
- **New phone-lib release** → bump version in `phone-lib/pyproject.toml`, tag `vX.Y.Z`, push — CI publishes when `ENABLE_PYPI=true`.
