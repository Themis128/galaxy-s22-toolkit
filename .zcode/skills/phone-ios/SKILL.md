---
name: phone-ios
description: iPhone/iPad support via libimobiledevice - info, iTunes-free backup/restore, screenshots, app list (no jailbreak)
version: 1.0.0
author: Galaxy S22+ Toolkit
tags:
  - ios
  - iphone
  - backup
  - libimobiledevice
---

# Phone iOS Skill

Wondershare's iOS management via the open-source libimobiledevice suite —
no iTunes, no jailbreak, no lock bypass.

## Commands

```bash
phone-ios info                 # name, model, iOS version, UDID
phone-ios backup [--full]      # idevicebackup2 to data/ios-backups/ (hours on first full)
phone-ios restore --dir D --yes  # wipes + replaces device content (typed confirm)
phone-ios screenshot           # data/artifacts/ios-<ts>.png
phone-ios apps                 # installed app list
```

## Prerequisites

- libimobiledevice CLI suite on PATH (`idevice_id` etc.) —
  <https://libimobiledevice.org> (Windows: Apple Mobile Device driver /
  usbmuxd required)
- `python tools/doctor.py` reports the `mobile:idevice_id` check

## Honest limits

- Restore replaces device content — typed `--yes` required.
- No activation/lock bypass of any kind (anti-theft exclusion).
