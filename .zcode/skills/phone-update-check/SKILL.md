---
name: phone-update-check
description: Check Android security patch age and open the system update screen on the phone
version: 1.0.0
author: Galaxy S22+ Toolkit
tags:
  - android
  - security
  - updates
---

# Phone Update Check

Reports the device's security-patch age with a verdict (OK / AGING / OUTDATED)
and can open the system update screen on the phone.

## Usage

```bash
# From the repo root
python tools/update_check.py                  # report (exit 1 if patch >90 days)
python tools/update_check.py --open-settings  # also opens Settings > Software update
```

## Notes

- Uses `diagnostics/config.yaml` wireless settings, like production code.
- Requires an attached device (USB or wireless ADB).
- Thresholds: <60 days OK, 60-90 AGING, >90 OUTDATED (exit 1).
