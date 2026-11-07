---
name: phone-mirror
description: Screen mirror and control the attached Galaxy via scrcpy (open source, no root) - view, interact, record the screen to data/mirrors/
version: 1.0.0
author: Galaxy S22+ Toolkit
tags:
  - android
  - scrcpy
  - screen-mirror
  - adb
---

# Phone Mirror Skill

Wondershare Screen Mirror equivalent using scrcpy (Genymobile, open source).
Works over USB and wireless ADB, no root required.

## Commands

```bash
phone-mirror start              # live mirror + control window
phone-mirror record             # mirror + record to data/mirrors/mirror-<ts>.mp4
phone-mirror stop               # kill running scrcpy
phone-mirror status             # binary, resolved serial, recordings
```

## Notes

- Serial resolution follows the toolkit standard (config.yaml
  `preferred_serial` wins; wireless auto-connect engages when nothing is
  attached).
- The dashboard container cannot launch host processes — the Mirror card
  shows the exact host command to paste.
