# Phone App Manager Skill

Manage installed apps on your Android device: list, clear data/cache, uninstall, disable/enable (freeze/unfreeze).

## Installation

```bash
pip install -e .
```

## Usage

```bash
# List apps
phone-app-manager list

# Clear app data
phone-app-manager clear com.example.app

# Uninstall app
phone-app-manager uninstall com.example.app

# Disable app (freeze)
phone-app-manager disable com.example.app

# Enable app (unfreeze)
phone-app-manager enable com.example.app

# Show app info
phone-app-manager info com.example.app
```

See [SKILL.md](SKILL.md) for full documentation.