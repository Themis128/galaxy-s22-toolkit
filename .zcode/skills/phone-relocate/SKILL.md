---
name: phone-relocate
description: Migrate the toolkit out of the OneDrive-synced path (dry-run plan, clone-based, re-registers scheduled tasks)
version: 1.0.0
author: Galaxy S22+ Toolkit
tags:
  - migration
  - onedrive
  - environment
---

# Phone Relocate

The durable fix for OneDrive's read-only re-flagging: move the repo out
of the synced tree. Clone-based, so git history stays intact; runtime
state (.env, logs, reports, backups) is carried over and the three
\Phone Toolkit\ scheduled tasks are re-registered to the new path.

## Usage

```bash
python tools/relocate_repo.py                 # print the plan (no changes)
python tools/relocate_repo.py --execute       # perform the migration
python tools/relocate_repo.py --target D:\code\s22toolkit --execute
```

## After --execute, finish by hand

1. `pip install -e <target>/phone-lib`
2. `docker compose down` (old tree) then `docker compose up -d --build`
   from the new tree
3. `python tools/doctor.py` from the new tree to verify
4. Only then delete the old OneDrive-synced tree

Close editors/terminals pointing at the old path first (this session
included). The tool refuses non-empty or OneDrive-synced targets.
