---
name: phone-logcat
description: Stream, filter, and export Android logcat logs with crash/ANR detection
version: 1.0.0
author: Galaxy S22+ Toolkit
tags:
  - android
  - adb
  - logcat
  - debugging
  - logs
---

# Phone Logcat Skill

Stream, filter, and export Android logcat logs from your connected device. Includes crash detection, ANR reports, and export capabilities.

## Commands

### `stream` - Stream live logcat
```bash
# Stream all logs
phone-logcat stream

# Filter by pattern
phone-logcat stream --pattern "MyApp" --pattern "Error"

# Filter by log level (V=Verbose, D=Debug, I=Info, W=Warn, E=Error, F=Fatal)
phone-logcat stream --level "WEF"

# Filter by tag
phone-logcat stream --tag "ActivityManager"

# Limit output
phone-logcat stream --count 50 --timeout 10

# JSON output for programmatic use
phone-logcat stream --json
```

### `errors` - Show recent errors and crashes
```bash
# Show combined error/ANR report
phone-logcat errors

# Show only ANRs
phone-logcat errors --anr

# Show only crashes
phone-logcat errors --crashes

# Limit count
phone-logcat errors --count 20

# JSON output
phone-logcat errors --json
```

### `export` - Export logs to file
```bash
# Export to specific file
phone-logcat export --output my_logs.txt

# Export logs from past N hours
phone-logcat export --past-hours 24 --output recent_logs.txt

# Export with event count
phone-logcat export --count 100 --output crash_report.txt
```

### `clear` - Clear device logs
```bash
phone-logcat clear
```

## Options

| Option | Description |
|--------|-------------|
| `--serial` | Device serial number (uses first connected if omitted) |
| `--json` | Output in JSON format |
| `--count` | Limit number of entries |
| `--timeout` | Timeout in seconds for streaming |
| `--pattern` | Filter patterns (can use multiple) |
| `--level` | Log levels to include (V,D,I,W,E,F) |
| `--tag` | Filter by log tag |
| `--output` | Output file path for export |
| `--past-hours` | Export logs from past N hours |
| `--pad-tags` | Pad tags to fixed width |

## Examples

```bash
# Watch for crashes in real-time
phone-logcat stream --level "EF" --tag "AndroidRuntime"

# Export yesterday's crash reports
phone-logcat export --past-hours 24 --output crash_dump.txt

# Check for ANRs
phone-logcat errors --anr --count 10
```

## Requirements
- ADB installed and in PATH
- USB debugging enabled on device
- Device authorized for ADB access