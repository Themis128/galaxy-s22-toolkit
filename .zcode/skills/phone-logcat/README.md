# Phone Logcat Skill

Stream, filter, and export Android logcat logs from your connected device. Includes crash detection, ANR reports, and export capabilities.

## Installation

```bash
pip install -e .
```

## Usage

```bash
# Stream live logs
phone-logcat stream

# Filter by level
phone-logcat stream --level "WEF"

# Show recent errors
phone-logcat errors

# Export logs
phone-logcat export --output logs.txt

# Clear device logs
phone-logcat clear
```

See [SKILL.md](SKILL.md) for full documentation.