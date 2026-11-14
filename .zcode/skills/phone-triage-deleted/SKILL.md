---
name: phone-triage-deleted
description: Read-only triage of deleted-file recovery candidates on a Galaxy phone (Samsung trash dirs, thumbnails) with honest root boundaries - the Wondershare deleted-file recovery entry point
version: 1.0.0
author: Galaxy S22+ Toolkit
tags:
  - android
  - recovery
  - triage
---

# Deleted-File Triage Skill

An honest "what is recoverable, and how" before committing to a recovery
flow. Read-only; every probe degrades to N/A rather than erroring.

## Commands

```bash
phone-triage-deleted scan   # trash item counts + bytes, thumbnails size
phone-triage-deleted deep   # root-gated extra pass (honest refusal unrooted)
```

## Recovery routes

- `phone-recover trash` — pull the soft-deleted items back (the real path)
- `phone data-eraser free-space` — secure-overwrite remnants instead
- deep/raw-partition carving is deliberately not implemented on FBE flash
