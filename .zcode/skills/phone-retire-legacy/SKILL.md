---
name: phone-retire-legacy
description: Verify the legacy OneDrive tree is fully superseded, export any data only it holds, and delete it safely
version: 1.0.0
author: Galaxy Toolkit
tags:
  - maintenance
  - onedrive
  - cleanup
---

# Legacy Tree Retirement

The toolkit's canonical tree is `C:\dev\galaxy-s22-toolkit` (GitHub,
PyPI, Docker). This skill retires the old OneDrive working copy at
`C:\Users\tbaltzakis\CrossDevice\Galaxy S22+ (2)` - safely.

## Usage

```bash
# From the repo root (C:\dev\galaxy-s22-toolkit)
python tools/decommission_legacy.py check    # read-only preflight (7 checks)
python tools/decommission_legacy.py export   # copy runtime data only legacy has
python tools/decommission_legacy.py delete   # dry-run with preflight
python tools/decommission_legacy.py delete --confirm   # delete for real
```

## The 7 preflight checks

1. canonical tree + git present
2. legacy HEAD is an ancestor of origin/master (nothing unique lost)
3. all 3 scheduled tasks point at the canonical tree
4. pip editable install resolves from canonical
5. docker container has no legacy-path references
6. canonical runtime data at least as fresh as legacy's
7. OneDrive placeholders (cloud-backed files) counted - they are
   recoverable from OneDrive's Recycle Bin (~30 days) after deletion

## Safety gates

- `delete` runs the full preflight first; any FAIL blocks deletion
- dry-run by default; `--confirm` required for the real deletion
- refuses to run when the current directory is inside the legacy tree
  (close ZCode sessions bound to the old path first)
- OneDrive placeholder/unreadable-file handling: hydration errors
  (winerror 362+, errno 22 reparse points) are classified as
  cloud-backed, never silently lost; readable-but-newer files block and
  must be exported first

## Notes

- The 8.4 GB tree includes `data/phone-mirror` personal files (WhatsApp
  backups, certificates). Placeholders among them are cloud-backed;
  readable ones must be exported first.
- After deletion, the OneDrive Recycle Bin holds the removed files for
  ~30 days as a final safety net.
