# phone-selective-restore

Selective restore from the incremental phone mirror
(`data/phone-mirror/`, maintained by `phone-backup`).

- `list` — per-root inventory (files + bytes) with an optional `--pattern`.
- `restore` — filter by `--roots`, `--pattern`, `--newer-than YYYY-MM-DD`;
  dry-run by default, `--yes` pushes to `/sdcard/<rel>`; remote files that
  already exist are skipped unless `--overwrite`.

Implementation: `tools/selective_restore.py` (+ `tools/test_selective_restore.py`).
