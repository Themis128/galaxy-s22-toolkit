# phone-triage-deleted

Read-only deleted-file triage (Wondershare deleted-file-recovery entry
point): Samsung trash dirs (`.trashed-*` counts via recover_media's
parser), `.thumbnails` size, and a root-gated `deep` mode that says so
honestly on unrooted devices. No mutation anywhere — recovery itself is
`phone-recover trash`, secure overwrite is the data eraser.

Implementation: `tools/deleted_file_triage.py` (+ `tools/test_deleted_file_triage.py`).
