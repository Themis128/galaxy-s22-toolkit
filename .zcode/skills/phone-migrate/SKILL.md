---
name: phone-migrate
description: Phone-to-phone migration wizard - export user content from the old Galaxy to a staging dir, push it onto the new one, and a checklist for what ADB cannot move
version: 1.0.0
author: Galaxy S22+ Toolkit
tags:
  - android
  - migration
  - adb
---

# Migration Wizard Skill

Move shared-storage user content between two Galaxy phones over ADB in
three gated steps. Honest about the boundary: contacts, message history,
WhatsApp chats and authenticator seeds need on-device flows.

## Commands

```bash
phone-migrate plan                 # read-only checklist from the attached phone
phone-migrate export --yes         # old phone -> data/migration/<ts>/
phone-migrate import --yes         # staging -> new phone (never overwrites)
```

## Two-device rule

With 2+ attached devices you must pass `--serial`; a single attached
device is auto-selected. `import` skips existing remote files unless
`--overwrite` AND `--yes`.
