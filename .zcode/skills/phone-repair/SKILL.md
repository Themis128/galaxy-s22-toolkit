---
name: phone-repair
description: Approved Android repair actions - storage cleanup, app management, network reset, log cleanup, with approval policy and persistent history
version: 1.0.0
author: Galaxy S22+ Toolkit
tags:
  - android
  - adb
  - repair
  - maintenance
  - storage
  - network
  - logcat
---

# Phone Repair Skill

Approved repair actions for the connected device. Approval policy comes from
`diagnostics/config.yaml` (`repair:`): low-risk actions flagged `auto_approve`
run directly; anything else needs explicit confirmation (toast with
Approve/Deny buttons when desktop notifications are enabled).

## Commands

### `list` - Show all available actions
```bash
phone-repair list
```

### `recommend` - Actions suggested by the latest diagnostics
```bash
phone-repair recommend
```

### `run` - Execute actions
```bash
# All auto-approve (low-risk) actions
phone-repair run auto

# Specific actions by name
phone-repair run flush_dns clear_logcat_buffers

# JSON output
phone-repair run auto --json
```

### `history` - Persisted repair history
```bash
phone-repair history
```

## Safety

- Every executed result is appended to `logs/repair_history.jsonl`
- Root-gated actions (tombstones, ANR traces) report an honest failure on
  unrooted devices instead of a silent no-op
- Network toggles always re-enable, so a half-failed reset never leaves
  Wi-Fi or mobile data off
- Non-auto actions return "not approved" unless explicitly approved
