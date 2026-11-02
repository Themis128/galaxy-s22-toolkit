---
name: phone-app-manager
description: Manage apps - list, clear data, uninstall, disable/enable
version: 1.0.0
author: Galaxy S22+ Toolkit
tags:
  - android
  - adb
  - apps
  - package-manager
---

# Phone App Manager Skill

Manage installed apps on your Android device: list, clear data/cache, uninstall, disable/enable (freeze/unfreeze).

## Commands

### `list` - List installed apps
```bash
# List enabled apps (default)
phone-app-manager list

# Include disabled apps
phone-app-manager list --disabled

# JSON output
phone-app-manager list --json
```

### `clear` - Clear app data and cache
```bash
phone-app-manager clear com.example.app
```

### `uninstall` - Uninstall an app
```bash
phone-app-manager uninstall com.example.app
```

### `disable` - Disable/freeze an app
```bash
phone-app-manager disable com.example.app
```

### `enable` - Enable/unfreeze an app
```bash
phone-app-manager enable com.example.app
```

### `info` - Show detailed app info
```bash
# Human readable
phone-app-manager info com.example.app

# JSON output
phone-app-manager info com.example.app --json
```

## Options

| Option | Description |
|--------|-------------|
| `--serial` | Device serial number (uses first connected if omitted) |
| `--json` | Output in JSON format (list, info commands) |
| `--disabled` | Include disabled apps in list |

## Examples

```bash
# List all apps including disabled
phone-app-manager list --disabled

# Clear cache/data for an app
phone-app-manager clear com.samsung.android.app.spage

# Freeze bloatware
phone-app-manager disable com.facebook.katana

# Unfreeze app
phone-app-manager enable com.facebook.katana

# Show app details
phone-app-manager info com.whatsapp
```

## Requirements
- ADB installed and in PATH
- USB debugging enabled on device
- Device authorized for ADB access