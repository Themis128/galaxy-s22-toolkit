# Galaxy S22+ Toolkit

Complete phone-management suite for a Samsung Galaxy S22+ (SM-S906B, Exynos international, rootable variant) over ADB: diagnostics, monitoring dashboard, approved auto-repair with desktop-toast approvals, file transfer, logcat, app management — plus guarded root support, **screen mirroring (scrcpy), device-file manager, resale-style verification, data recovery (trash + root-gated WhatsApp decrypt), WhatsApp official transfer guide, iPhone/iPad support (libimobiledevice), and a triple-gated Samsung firmware-repair wizard**. Adapts to any Galaxy S/Note/A on Android 10+ via the multi-Galaxy compatibility layer. Reaches the phone over USB or wireless ADB through Tailscale, with auto-reconnect after reboots. The Dockerized dashboard is **live on the tailnet** at `http://100.83.120.93:8081`.

> **Root warning**: rooting requires unlocking the bootloader, which permanently
> wipes data and trips the Knox eFuse (Samsung Pay/Wallet, Secure Folder, Samsung
> Pass are lost forever). Read [rooting/RUNBOOK.md](rooting/RUNBOOK.md) before deciding.

## Quickstart

```bash
# 1. Install everything (20 skills + rooting)
bash galaxy-s22-toolkit-skills/install.sh

# Quickstart
phone-diagnostics device        # verify connectivity + identity
phone-diagnostics run           # full health report
phone-repair recommend          # repair actions suggested by diagnostics
phone-repair run auto           # run all low-risk repairs (approval policy)
phone-app-manager list          # installed apps
phone-logcat errors --json      # crash/ANR detection
phone-insights                  # degradation insights from metrics history

# Real-time monitoring dashboard (8080 is occupied by another service here)
python dashboard/app.py         # from repo root; serves http://127.0.0.1:8081

# Or in Docker (reaches the phone over wireless ADB through the tailnet)
docker compose up -d --build    # host networking; live at 100.83.120.93:8081
```

## Commands

| Command | What it does |
|---|---|
| `phone-mirror start\|record\|stop` | Screen mirror & control via scrcpy (no root) |
| `phone-verify` | Resale-style verification report (score /100, JSON+HTML) |
| `phone-recover trash` | Pull MediaStore trash/deleted media (no root) |
| `phone-recover whatsapp --confirm-key` | Root-gated WhatsApp backup decrypt + chat export |
| `phone-whatsapp check\|guide` | Official WhatsApp QR chat-transfer guide |
| `phone-ios info\|backup\|restore\|screenshot\|apps` | iPhone/iPad via libimobiledevice (no jailbreak) |
| `phone-repair-system check\|flash` | Samsung firmware repair wizard (Heimdall, triple-gated) |
| `phone-diagnostics run` | Full health report (battery, storage, thermal, network, logcat) |
| `phone-diagnostics device` | Device identity & OS info |
| `phone-insights` | Battery drain rate, storage growth ETA, p95 memory/thermal verdicts |
| `phone-update-check` | Security-patch age verdict; `--open-settings` opens the system update screen |
| `phone-doctor` | Environment health (ADB, tasks, backups, OneDrive artifacts) |
| `phone-connect status\|connect\|reconnect` | Wireless ADB over Tailscale control |
| `phone-relocate` | Move the repo out of OneDrive (dry-run default, `--execute`) |
| `phone-system-update status\|open` | OTA update driver (status works locked; open needs the device unlocked) |
| `phone-retire-legacy` | Retire the legacy OneDrive tree (dry-run default; `--execute` from outside the tree) |
| `phone-remote-control` | Dashboard REST API client (`--allow-private` for localhost; SSRF-guarded) |
| `phone-screen-control screenshot` | Capture PNG |
| `phone-screen-control record --time 30` | 30 s screen recording |
| `phone-file-transfer pull /sdcard/DCIM/Camera ./data/pulls` | Pull files with progress |
| `phone-file-transfer push <local> <remote>` | Push files |
| `phone-logcat errors` | Crash/ANR detection |
| `phone-logcat stream --tag <TAG>` | Live log stream |
| `phone-app-manager list` | Installed apps |
| `phone-app-manager clear <pkg>` | Clear app data |
| `phone-repair list` | All repair actions with risk levels |
| `phone-repair recommend` | Actions suggested by the latest diagnostics |
| `phone-repair run auto` | Run all low-risk repairs (approval policy, JSONL history) |
| `phone-repair run flush_dns clear_logcat_buffers` | Run specific repairs |
| `phone-repair history` | Persisted repair history |
| `phone-root preflight` | Root-readiness GO/NO-GO report |
| `phone-root backup` | Full pre-flash backup |
| `phone-root verify` | Post-flash root verification |
| `phone-root modules list` | Magisk module management |

## Repository layout

```
├── ARCHITECTURE.md      # topology, layer diagram, API contract, safety model
├── phone-lib/           # Layer 1: typed ADB wrapper (pkg name: galaxy-s22-toolkit)
├── diagnostics/         # Layer 2: scheduled health checks + config.yaml
│                        #          (schtasks: daily 03:00 diagnostics, 03:30 backup,
│                        #           03:45 rollup — silent, registered)
├── tools/               # 13 standalone utilities (doctor, insights, alerts,
│                        #          backup/restore, dashboard_client, relocate_repo, …)
├── .zcode/skills/       # Layer 3: 12 CLI skills (phone-diagnostics, phone-repair,
│                        #          phone-insights, phone-connect, phone-screen-control,
│                        #          phone-file-transfer, phone-logcat, phone-app-manager,
│                        #          phone-update-check, phone-doctor, phone-relocate,
│                        #          phone-remote-control)
├── rooting/             # 13th package: phone-root CLI + RUNBOOK.md
├── dashboard/           # Layer 4: FastAPI + WebSocket + Chart.js (+ Dockerfile, README)
├── docker-compose.yml   # containerized dashboard over tailnet wireless ADB (host network)
├── galaxy-s22-toolkit-skills/   # unified installer (install.sh) — Devin-ready
├── scripts/             # termux bootstrap, wireless ADB setup, cleanup helpers
├── adb-workflow.sh|ps1  # original workflow scripts (reference)
├── data/                # runtime output (gitignored): phone-mirror, reports, artifacts
└── logs/                # diagnostics log + repair_history.jsonl (gitignored)
```

Canonical location of this repo: `C:\dev\galaxy-s22-toolkit` (relocated out of
OneDrive; the old tree is legacy). Keep it outside synced folders — OneDrive's
read-only re-flagging corrupts live databases and git internals.

## For agents (Devin / ZCode)

The 12 skills + rooting are pip-installed console commands, so any agent can use them
directly after one command:

```bash
bash galaxy-s22-toolkit-skills/install.sh
```

Details: [ARCHITECTURE.md](ARCHITECTURE.md) (topology, data flow, API contract, safety model).

## PyPI Publishing (Trusted Publishing)

The `phone-lib` package (`galaxy-s22-toolkit`) is published to PyPI using GitHub Actions with OIDC trusted publishing — no API tokens required.

### One-time setup

1. **Create the project on PyPI** (if not already):
   - Go to <https://pypi.org/manage/projects/> → "Add project"
   - Reserve the name `galaxy-s22-toolkit` (or your chosen name)
   - Leave it empty — the first publish will create it

2. **Configure trusted publisher** on PyPI:
   - Go to your project → "Publishing" → "Add publisher"
   - **PyPI project name**: `galaxy-s22-toolkit`
   - **Owner**: your GitHub username/org (e.g., `tbaltzakis`)
   - **Repository name**: `Galaxy S22+ (2)` (exact repo name)
   - **Workflow name**: `publish.yml` (or `ci.yml` if combined)
   - **Environment name**: `pypi` (optional but recommended)

3. **Add GitHub Environment** (optional, for protection rules):
   - Repo → Settings → Environments → New environment: `pypi`
   - Add required reviewers, wait timers, or branch restrictions

4. **Enable in GitHub Actions**:
   - Set repository variable `ENABLE_PYPI = "true"` (Settings → Variables → Actions)
   - The workflow `.github/workflows/publish.yml` only runs when this is set

### Publishing flow

```bash
# Tag a version locally
git tag v0.3.1
git push origin v0.3.1
```

The `publish.yml` workflow:
- Runs on tag push matching `v*`
- Builds wheel with `pip wheel .`
- Publishes via `pypa/gh-action-pypi-publish@release/v1` (OIDC)
- Only executes when `ENABLE_PYPI=true`

### Local test build

```bash
cd phone-lib
pip install build
python -m build --wheel
# Inspect dist/galaxy_s22_toolkit-*.whl
```

## License

Personal project — no license.
