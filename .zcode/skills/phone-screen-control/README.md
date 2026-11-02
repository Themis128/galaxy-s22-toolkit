# Phone Screen Control Skill

Control your Android device screen: take screenshots, record screen, get UI hierarchy dumps, and simulate input (tap, swipe, text, key events).

## Installation

```bash
pip install -e .
```

## Usage

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

See [SKILL.md](SKILL.md) for full documentation.