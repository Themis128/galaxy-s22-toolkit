---
name: phone-file-transfer
description: Transfer files between device and computer with progress bars
version: 1.0.0
author: Galaxy S22+ Toolkit
tags:
  - android
  - adb
  - file-transfer
  - pull
  - push
---

# Phone File Transfer Skill

Transfer files between your Android device and computer with progress bars, size formatting, and JSON output.

## Commands

### `pull` - Pull file from device to local
```bash
# Pull file to current directory
phone-file-transfer pull /sdcard/Download/photo.jpg

# Pull to specific local path
phone-file-transfer pull /sdcard/Download/photo.jpg ./photos/
```

### `push` - Push file from local to device
```bash
# Push file to device
phone-file-transfer push ./photo.jpg /sdcard/Pictures/
```

### `list` - List files on device
```bash
# List files in default directory (/sdcard)
phone-file-transfer list

# List files in specific directory
phone-file-transfer list /sdcard/Download

# JSON output
phone-file-transfer list --json
```

### `delete` - Delete file on device
```bash
# Delete with confirmation
phone-file-transfer delete /sdcard/Download/old_file.txt

# Force delete without confirmation
phone-file-transfer delete /sdcard/Download/old_file.txt --force
```

### `mkdir` - Create directory on device
```bash
phone-file-transfer mkdir /sdcard/MyFolder/SubFolder
```

## Options

| Option | Description |
|--------|-------------|
| `--serial` | Device serial number (uses first connected if omitted) |
| `--json` | Output in JSON format (list command) |
| `--force`, `-f` | Force delete without confirmation |

## Examples

```bash
# Backup photos
phone-file-transfer pull /sdcard/DCIM/Camera ./backup/photos/

# Transfer APK to device
phone-file-transfer push ./app-release.apk /sdcard/Download/

# List downloads
phone-file-transfer list /sdcard/Download --json

# Clean up old files
phone-file-transfer delete /sdcard/Download/old.apk --force
```

## Requirements
- ADB installed and in PATH
- USB debugging enabled on device
- Device authorized for ADB access