---
name: phone-connect
description: Manage wireless ADB connection to the Galaxy S22+ - status, connect, reconnect over Wi-Fi/tailnet
version: 1.0.0
author: Galaxy S22+ Toolkit
tags:
  - android
  - adb
  - wireless
  - connectivity
---

# Phone Connect

Manages the wireless ADB connection using the toolkit's config-driven
resolution (diagnostics/config.yaml: preferred USB serial wins, tailnet
host auto-connect).

## Usage

```bash
python tools/adb_connect.py status      # attached transports + resolved serial
python tools/adb_connect.py connect     # connect + verify model/battery
python tools/adb_connect.py reconnect   # drop Wi-Fi transport and redo it
```

## Notes

- `reconnect` recovers the common failure: adb server restarted or the
  phone's TCP listener reset - it drops the stale transport and
  auto-connects via the configured host.
- Exit code 1 when nothing is attached and auto-connect fails.
