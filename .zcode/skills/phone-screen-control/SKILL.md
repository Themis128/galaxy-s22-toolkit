---
name: phone-screen-control
description: Control Android device screen - screenshot, screen record, UI dump, input control
version: 1.0.0
author: Galaxy S22+ Toolkit
tags:
  - android
  - adb
  - screen
  - screenshot
  - screenrecord
  - ui-dump
  - input
---

# Phone Screen Control Skill

Control your Android device screen: take screenshots, record screen, get UI hierarchy dumps, and simulate input (tap, swipe, text, key events).

## Commands

### `screenshot` - Take screenshot and pull to local
```bash
# Save to current directory with auto-generated filename
phone-screen-control screenshot

# Save to specific directory
phone-screen-control screenshot -o /path/to/output

# Custom filename
phone-screen-control screenshot -f my_screenshot.png

# JSON output
phone-screen-control screenshot --json
```

### `record` - Record screen and pull to local
```bash
# Record 180 seconds (default max) to current directory
phone-screen-control record

# Custom duration (max 180 seconds)
phone-screen-control record -t 60

# Custom bit rate and size
phone-screen-control record -b 8000000 --size 1920x1080

# Custom output directory and filename
phone-screen-control record -o /path/to/output -f demo.mp4

# JSON output
phone-screen-control record --json
```

### `ui-dump` - Get UI hierarchy dump
```bash
# Print UI dump to stdout
phone-screen-control ui-dump

# Pull dump to local file
phone-screen-control ui-dump --pull -o /path/to/output

# Compressed dump
phone-screen-control ui-dump --compressed

# JSON output
phone-screen-control ui-dump --json
```

### `tap` - Tap screen coordinates
```bash
phone-screen-control tap 500 1000

# JSON output
phone-screen-control tap 500 1000 --json
```

### `swipe` - Swipe between coordinates
```bash
# Default 300ms duration
phone-screen-control swipe 100 500 900 500

# Custom duration
phone-screen-control swipe 100 500 900 500 -d 500

# JSON output
phone-screen-control swipe 100 500 900 500 --json
```

### `text` - Type text into focused field
```bash
phone-screen-control text "Hello World"

# JSON output
phone-screen-control text "Hello World" --json
```

### `keyevent` - Send key event
```bash
# By key name
phone-screen-control keyevent KEYCODE_BACK

# By key code
phone-screen-control keyevent 4

# JSON output
phone-screen-control keyevent KEYCODE_HOME --json
```

### `display-info` - Get display information
```bash
# Human readable
phone-screen-control display-info

# JSON output
phone-screen-control display-info --json
```

### `orientation` - Get or set screen orientation
```bash
# Get current orientation
phone-screen-control orientation

# Set orientation (0=default, 1=landscape, 2=portrait, 3=reverse landscape, 4=reverse portrait)
phone-screen-control orientation --set 1

# JSON output
phone-screen-control orientation --json
```

### `density` - Get or set screen density
```bash
# Get current density
phone-screen-control density

# Set density (requires reboot to persist)
phone-screen-control density --set 480

# Reset to default
phone-screen-control density --reset

# JSON output
phone-screen-control density --json
```

### `bugreport` - Take bugreport and pull to local
```bash
phone-screen-control bugreport

# Custom output directory
phone-screen-control bugreport -o /path/to/output

# JSON output
phone-screen-control bugreport --json
```

### `press` - Press hardware key
```bash
phone-screen-control press back
phone-screen-control press home
phone-screen-control press recent
phone-screen-control press power
phone-screen-control press volume_up
phone-screen-control press volume_down

# JSON output
phone-screen-control press home --json
```

## Options

| Option | Description |
|--------|-------------|
| `--serial`, `-s` | Device serial number (uses first connected if omitted) |
| `--json`, `-j` | Output in JSON format |
| `-o`, `--output` | Output directory (default: current directory) |
| `-f`, `--filename` | Output filename (auto-generated if omitted) |
| `-t`, `--time-limit` | Recording time limit in seconds (max 180, default: 180) |
| `-b`, `--bit-rate` | Video bit rate in bps (default: 4000000) |
| `--size` | Video size (e.g., 1920x1080) |
| `--pull` | Pull UI dump to local file |
| `--compressed` | Compressed UI dump |
| `-d`, `--duration` | Swipe duration in ms (default: 300) |
| `--set` | Set value (orientation: 0-4, density: DPI value) |
| `--reset` | Reset density to default |

## Examples

```bash
# Take a screenshot
phone-screen-control screenshot

# Record a 30-second demo
phone-screen-control record -t 30 -f demo.mp4

# Get UI hierarchy for debugging
phone-screen-control ui-dump --pull -o ./ui_dumps

# Tap a button at coordinates
phone-screen-control tap 540 1800

# Swipe to unlock
phone-screen-control swipe 540 1800 540 600 -d 500

# Type text in a field
phone-screen-control text "search query"

# Send back key
phone-screen-control keyevent KEYCODE_BACK

# Get display info
phone-screen-control display-info

# Lock screen orientation to portrait
phone-screen-control orientation --set 2

# Take bugreport for debugging
phone-screen-control bugreport
```

## Requirements

- ADB installed and in PATH
- USB debugging enabled on device
- Device authorized for ADB access
- For screen recording: Android 4.4+ (API 19+)
- For density/orientation changes: may require reboot to persist