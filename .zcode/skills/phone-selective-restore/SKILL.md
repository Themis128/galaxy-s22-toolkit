---
name: phone-selective-restore
description: Push selected files from the phone mirror back onto a Galaxy phone - the Wondershare selective-restore equivalent (dry-run first, never overwrites unless asked)
version: 1.0.0
author: Galaxy S22+ Toolkit
tags:
  - android
  - restore
  - adb
---

# Selective Restore Skill

Restore chosen shared-storage content from `data/phone-mirror/` back onto
a phone over ADB. Dry-run first; existing remote files are skipped unless
`--overwrite`.

## Commands

```bash
phone-selective-restore list --pattern "*.jpg"   # what the mirror can restore
phone-selective-restore restore --roots DCIM,Pictures --newer-than 2026-01-01
phone-selective-restore restore --pattern "*.jpg" --yes   # execute pushes
```

## Honesty note

Shared-storage content only (photos, videos, downloads...). App data and
app-private files CANNOT be restored over ADB (adb backup is dead); those
need per-app restore flows or Smart Switch.
