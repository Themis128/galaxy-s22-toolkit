---
name: phone-backup
description: Incremental wireless phone backup (photos/videos/messages/WhatsApp media) into data/phone-mirror with a JSON manifest - the Wondershare My Backup equivalent
version: 1.0.0
author: Galaxy S22+ Toolkit
tags:
  - android
  - backup
  - incremental
  - adb
---

# Phone Backup Skill

Incremental, scheduled, local-only phone backup over ADB (USB or wireless).

## Commands

```bash
phone-backup incremental   # pull only new/changed files (manifest-driven)
phone-backup full          # pull everything, refresh the manifest
phone-backup status        # last-run report (also read by the dashboard)
```

## Coverage

DCIM, Pictures, Movies, Download, Documents, Recordings, Ringtones, Music,
plus WhatsApp / WhatsApp Business media (Android/media). Trash, thumbnails
and caches are skipped.

## Scheduling

Nightly task `\Phone Toolkit\Phone Backup` (03:15, pythonw, silent) keeps
the mirror current; the dashboard Backup card reads the status file.
