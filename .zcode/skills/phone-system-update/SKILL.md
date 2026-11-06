---
name: phone-system-update
description: Drive the OTA system-update flow over ADB - open the update screen, tap Download and install, monitor, and install (with reboot) when ready
version: 1.0.0
author: Galaxy Toolkit
tags:
  - android
  - security
  - ota
  - updates
---

# Phone System Update Driver

Automates every ADB-reachable step of the Samsung OTA flow: wake the
screen, open Settings > Software update, tap **Download and install**,
and later tap **Install now** (reboots the phone). The final install
confirmation must be authorized with an explicit flag — the phone
reboots.

## Usage

```bash
# From the repo root (C:\dev\galaxy-s22-toolkit)
python tools/system_update.py status                  # patch-age verdict
python tools/system_update.py open                    # open the update screen
python tools/system_update.py ui                      # dump readable UI tree
python tools/system_update.py download                # dry-run: locate the button
python tools/system_update.py download --confirm      # start the OTA download
python tools/system_update.py install --confirm-reboot  # tap Install now (REBOOTS)
```

## Flow

1. `status` — patch age verdict (exit 1 while OUTDATED)
2. `download --confirm` — starts the download in the background (no
   reboot; the download continues on its own)
3. When the download finishes, Samsung shows an Install prompt —
   `install --confirm-reboot` taps it; battery >= 30% required
4. After the reboot, `status` shows the new patch date; wireless ADB
   auto-reconnects (`create_client(auto_connect=True)`)

## Safety gates

- Dry-run by default: `download`/`tap`/`install` print the target and
  exit 2 without `--confirm` / `--confirm-reboot`
- Lockscreen detection: aborts when the phone is locked (unlock first)
- Battery floor: install refuses below 30%
- Uses `diagnostics/config.yaml` wireless settings, like production code
