# Phone File Transfer Skill

Transfer files between your Android device and computer with progress bars, size formatting, and JSON output.

## Installation

```bash
pip install -e .
```

## Usage

```bash
# Pull file from device
phone-file-transfer pull /sdcard/Download/photo.jpg

# Push file to device
phone-file-transfer push ./photo.jpg /sdcard/Pictures/

# List files
phone-file-transfer list /sdcard/Download --json

# Delete file
phone-file-transfer delete /sdcard/Download/old.txt --force

# Create directory
phone-file-transfer mkdir /sdcard/MyFolder
```

See [SKILL.md](SKILL.md) for full documentation.