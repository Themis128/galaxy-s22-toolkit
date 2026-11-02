---
name: phone-diagnostics
description: Comprehensive Android device health diagnostics - battery, storage, network, thermal, crashes/ANRs
version: 1.0.0
author: Galaxy S22+ Toolkit
tags:
  - android
  - adb
  - diagnostics
  - health-check
  - battery
  - storage
  - network
  - thermal
  - logcat
  - crashes
  - anr
---

# Phone Diagnostics Skill

Comprehensive health check for Android devices: battery health, storage usage, network connectivity, thermal status, and crash/ANR detection from logcat.

## Commands

### `run` - Run full diagnostic suite
```bash
# Full diagnostic report (human readable)
phone-diagnostics run

# Full diagnostic report (JSON)
phone-diagnostics run --json

# Custom log check window (default: 60 minutes)
phone-diagnostics run --log-minutes 120

# Quiet mode with JSON output
phone-diagnostics run --json --quiet
```

### `device` - Show device info only
```bash
# Human readable
phone-diagnostics device

# JSON output
phone-diagnostics device --json
```

### `battery` - Show battery health only
```bash
# Human readable
phone-diagnostics battery

# JSON output
phone-diagnostics battery --json
```

### `storage` - Show storage usage only
```bash
# Human readable
phone-diagnostics storage

# JSON output
phone-diagnostics storage --json
```

### `logs` - Show crashes/ANRs from logcat only
```bash
# Last 60 minutes (default)
phone-diagnostics logs

# Custom time window
phone-diagnostics logs -m 120

# JSON output
phone-diagnostics logs --json
```

### `network` - Show network connectivity only
```bash
# Human readable
phone-diagnostics network

# JSON output
phone-diagnostics network --json
```

### `thermal` - Show thermal status only
```bash
# Human readable
phone-diagnostics thermal

# JSON output
phone-diagnostics thermal --json
```

## Options

| Option | Description |
|--------|-------------|
| `--serial`, `-s` | Device serial number (uses first connected if omitted) |
| `--json`, `-j` | Output in JSON format |
| `--quiet`, `-q` | Suppress progress output (useful with `--json`) |
| `--log-minutes` | Minutes of logs to check for crashes/ANRs (default: 60) |
| `-m`, `--minutes` | Minutes of logs to check (for `logs` command) |

## Examples

```bash
# Full diagnostic report
phone-diagnostics run

# Quick battery check
phone-diagnostics battery

# Check for crashes in last 2 hours
phone-diagnostics logs -m 120

# Network status as JSON for scripting
phone-diagnostics network --json

# Full report as JSON for automation
phone-diagnostics run --json --quiet
```

## Requirements

- ADB installed and in PATH
- USB debugging enabled on device
- Device authorized for ADB access
- For logcat access: Android 4.1+ (API 16+)
- For battery stats: requires `dumpsys batterystats` permission (usually available)
- For thermal zones: requires reading `/sys/class/thermal/` (usually available)