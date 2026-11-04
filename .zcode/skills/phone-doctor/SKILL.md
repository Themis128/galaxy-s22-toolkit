---
name: phone-doctor
description: Environment health check - OneDrive flags, junk files, adb, WSL, git hooks, dashboard container
version: 1.0.0
author: Galaxy S22+ Toolkit
tags:
  - environment
  - troubleshooting
  - onedrive
  - adb
---

# Phone Doctor

Catches the environment-bug class this repo keeps hitting in one command.

## Usage

```bash
python tools/doctor.py        # report (exit 1 on failures)
python tools/doctor.py --fix  # apply safe fixes (attr clear, junk delete)
```

## Checks

1. adb present + devices attached
2. OneDrive read-only flags (fixable with --fix)
3. mangled U+F03A junk files (fixable with --fix)
4. git pre-commit hook installed
5. WSL distros installed (read-only report)
6. dashboard container status
