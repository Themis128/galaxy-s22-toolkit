# Galaxy S22+ Toolkit

Complete phone-management suite for a Samsung Galaxy S22+ (SM-S906B, Exynos international, rootable variant) over ADB: diagnostics, monitoring dashboard, file transfer, logcat, app management — plus guarded root support.

> **Root warning**: rooting requires unlocking the bootloader, which permanently
> wipes data and trips the Knox eFuse (Samsung Pay/Wallet, Secure Folder, Samsung
> Pass are lost forever). Read [rooting/RUNBOOK.md](rooting/RUNBOOK.md) before deciding.

## Quickstart

```bash
# 1. Install everything (phone-lib + 5 skills + rooting)
bash galaxy-s22-toolkit-skills/install.sh

# Quickstart
phone-diagnostics device        # verify connectivity + identity
phone-diagnostics run           # full health report
phone-app-manager list          # installed apps
phone-logcat errors --json      # crash/ANR detection

# Real-time monitoring dashboard
python -m uvicorn dashboard.app:app --host 127.0.0.1 --port 8080   # from repo root
```

## Commands

| Command | What it does |
|---|---|
| `phone-diagnostics run` | Full health report (battery, storage, thermal, network, logcat) |
| `phone-diagnostics device` | Device identity & OS info |
| `phone-screen-control screenshot` | Capture PNG |
| `phone-screen-control record --time 30` | 30 s screen recording |
| `phone-file-transfer pull /sdcard/DCIM/Camera ./data/pulls` | Pull files with progress |
| `phone-file-transfer push <local> <remote>` | Push files |
| `phone-logcat errors` | Crash/ANR detection |
| `phone-logcat stream --tag <TAG>` | Live log stream |
| `phone-app-manager list` | Installed apps |
| `phone-app-manager clear <pkg>` | Clear app data |
| `phone-root preflight` | Root-readiness GO/NO-GO report |
| `phone-root backup` | Full pre-flash backup |
| `phone-root verify` | Post-flash root verification |
| `phone-root modules list` | Magisk module management |

## Repository layout

```
├── ARCHITECTURE.md      # layer diagram, API contract, safety model
├── phone-lib/           # Layer 1: typed ADB wrapper (pkg name: galaxy-s22-toolkit)
├── diagnostics/         # Layer 2: scheduled health checks + config.yaml
├── .zcode/skills/       # Layer 3: 5 CLI skills (phone-diagnostics, phone-screen-control,
│                        #          phone-file-transfer, phone-logcat, phone-app-manager)
├── rooting/             # 6th package: phone-root CLI + RUNBOOK.md
├── dashboard/           # Layer 4: FastAPI + WebSocket + Chart.js
├── galaxy-s22-toolkit-skills/   # unified installer (install.sh) — Devin-ready
├── scripts/             # termux bootstrap, wireless ADB setup, cleanup helpers
├── adb-workflow.sh|ps1  # original workflow scripts (reference)
├── data/                # runtime output (gitignored): phone-mirror, reports, artifacts
└── storage/             # legacy OneDrive placeholder dir — do not use
```

## storage/ directory (legacy)

`storage/` is a leftover OneDrive placeholder directory from earlier sessions. Its
files exist only in the cloud and cannot be moved/read while the cloud provider is
down. Phone data pulled from the device now lives in `data/phone-mirror/`. When
OneDrive is running, finish the cleanup:

```powershell
powershell -File scripts/finish-storage-cleanup.ps1
```

## For agents (Devin / ZCode)

The 5 skills + rooting are pip-installed console commands, so any agent can use them
directly after one command:

```bash
bash galaxy-s22-toolkit-skills/install.sh
```

Details: [ARCHITECTURE.md](ARCHITECTURE.md) (data flow, API contract, safety model).

## License

Personal project — no license.
