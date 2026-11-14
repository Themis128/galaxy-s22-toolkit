# phone-migrate

Phone-to-phone migration over ADB (Wondershare migration-wizard
equivalent): `plan` (read-only checklist) → `export --yes` (old phone →
`data/migration/<ts>/`) → `import --yes` (staging → new phone; never
overwrites unless `--overwrite` AND `--yes`).

Implementation: `tools/migration_wizard.py` (+ `tools/test_migration_wizard.py`).
