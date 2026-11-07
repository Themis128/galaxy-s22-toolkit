---
name: phone-recover
description: Data recovery - pull trash/deleted media (no root) and root-gated WhatsApp backup decryption + chat export
version: 1.0.0
author: Galaxy S22+ Toolkit
tags:
  - android
  - recovery
  - whatsapp
  - root
---

# Phone Recover Skill

Wondershare Data Recovery equivalent, in two honest tiers.

## Tier A — no root

```bash
phone-recover trash
```

Pulls MediaStore trash entries (`.trashed-*` under DCIM/Download/Pictures/
Movies) into `data/recovered/`.

## Tier B — root-gated

```bash
phone-recover whatsapp               # reports the required steps
phone-recover whatsapp --confirm-key # extracts the key via root + decrypts
```

Pulls the newest `msgstore.db.crypt*`, extracts the WhatsApp key via `su`
(explicit `--confirm-key`), decrypts with
[wa-crypt-tools](https://github.com/ElDavoo/wa-crypt-tools) (`pip install
wa-crypt-tools`), and exports up to 5000 messages to JSON under
`data/recovered/whatsapp/`.

Deep unallocated-space scans (raw block I/O) are documented in
`rooting/RUNBOOK.md` and deliberately not automated.

On an unrooted phone Tier B reports `requires_root` with the Knox warning —
it never pretends to succeed.
