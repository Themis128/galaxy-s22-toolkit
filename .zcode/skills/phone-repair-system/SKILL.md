---
name: phone-repair-system
description: Samsung System Repair wizard - stock firmware validation and triple-gated Heimdall flash (backup-first, brick warning)
version: 1.0.0
author: Galaxy S22+ Toolkit
tags:
  - android
  - samsung
  - heimdall
  - firmware
  - repair
---

# Phone Repair-System Skill

Wondershare System Repair equivalent for Samsung phones, built on the
open-source Heimdall (Odin protocol).

## Commands

```bash
phone-repair-system check                 # heimdall + device + mode report
phone-repair-system firmware --file FW.tar.md5   # list partitions inside
phone-repair-system flash --file FW.tar.md5 --partitions boot,vendor_boot --yes
```

## Safety model (triple gate)

1. `--yes` is required — without it the tool refuses.
2. The firmware must be a validated `.tar.md5` for the EXACT model/CSC.
3. A fresh `phone-root backup` (<24 h, `data/backup-*/`) must exist unless
   `--skip-backup-check` is passed knowingly.

An interrupted flash can brick the device. Nothing is flashed without the
typed Enter confirmation at the flash step. Knox note: flashing stock
firmware does not unlock or root anything, but the brick risk is real.
