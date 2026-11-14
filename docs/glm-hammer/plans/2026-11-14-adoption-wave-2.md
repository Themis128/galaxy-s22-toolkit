# Plan — Wondershare adoption wave 2, 2026-11-14

Adopts the four remaining ranked Wondershare candidates as tools + ZCode
skills, following the data-eraser pattern (gated CLI tool, pure parsers,
hermetic tests, skill shim). Forge critic panels are unsatisfiable in this
environment (documented); this plan self-certifies via its own gates.

Recon-verified interfaces: `tools/backup_phone.py` `load_manifest()` /
`save_manifest()` (mirror `data/phone-mirror/<Root>/<rel>`, manifest
rel -> {size, mtime}); `AdbClient.push/pull`; `tools/binfind.py`
`find_binary(name, winget_id)` (ffmpeg winget id `Gyan.FFmpeg`);
`tools/recover_media.py` `TRASH_DIRS` + `parse_trashed_name()`; skill shim
= 4 files under `.zcode/skills/<name>/` with parents[4] importlib
delegation.

### Task 1: Selective restore — `tools/selective_restore.py`

**Dependencies:** None

**Files:**
- Create: `tools/selective_restore.py`
- Test: `tools/test_selective_restore.py`
- Create: `.zcode/skills/phone-selective-restore/pyproject.toml`
- Create: `.zcode/skills/phone-selective-restore/phone_selective_restore/__init__.py`
- Create: `.zcode/skills/phone-selective-restore/SKILL.md`
- Create: `.zcode/skills/phone-selective-restore/README.md`

**Acceptance Criteria:**
- [ ] Subcommands `list` (per-root file count + bytes from the mirror, `--pattern` fnmatch filter) and `restore` (push mirror files to `/sdcard/<rel>` on the phone).
- [ ] Filters `--roots` (comma list), `--pattern`, `--newer-than YYYY-MM-DD` combine with AND; zero matches exits 0 printing "nothing to restore".
- [ ] `restore` is dry-run by default: prints the planned pushes (capped display, full count) and requires `--yes` to execute.
- [ ] Remote-exists conflict -> skip unless `--overwrite`; every skip reported in the summary.
- [ ] Pure helpers importable without a device: `iter_mirror_files(mirror_root)`, `filter_files(files, roots, pattern, newer_than)`, `plan_restore(files, remote_exists)`.
- [ ] ruff + ruff format --check + mypy --strict clean on tool and test; pytest on the test file green.

**Step 1:** Implement tool, helpers, tests, skill shim.
**Step 2:** Static checks + tests green; live `list` against the real mirror.

### Task 2: Migration wizard — `tools/migration_wizard.py`

**Dependencies:** 1

**Files:**
- Create: `tools/migration_wizard.py`
- Test: `tools/test_migration_wizard.py`
- Create: `.zcode/skills/phone-migrate/pyproject.toml`
- Create: `.zcode/skills/phone-migrate/phone_migrate/__init__.py`
- Create: `.zcode/skills/phone-migrate/SKILL.md`
- Create: `.zcode/skills/phone-migrate/README.md`

**Acceptance Criteria:**
- [ ] Subcommands: `plan` (read-only migration checklist from the attached device), `export` (pull user-content roots from the phone into `data/migration/<ts>/`), `import` (push staged files back to `/sdcard/<rel>`).
- [ ] Two-device rule: with 2+ attached devices and no `--serial`, refuse with a clear message; `--serial` selects; a single attached device auto-selects.
- [ ] `import` never overwrites: remote-exists -> skip (honest summary); `--overwrite` only takes effect with `--yes`.
- [ ] `export` and `import` are dry-run by default (count + size preview); `--yes` executes; `plan` is always read-only.
- [ ] The checklist names what ADB cannot move: contacts (Google sync / Smart Switch), WhatsApp (official QR, pointer to phone-whatsapp guide), authenticator seeds.
- [ ] ruff + ruff format --check + mypy --strict clean; pytest green; live smoke: export of a small root (Ringtones) from the S22+ with --yes.

**Step 1:** Implement tool, helpers, tests, skill shim.
**Step 2:** Static checks + tests green; live export smoke on the S22+.

### Task 3: Media repair — `tools/media_repair.py`

**Dependencies:** None

**Files:**
- Create: `tools/media_repair.py`
- Test: `tools/test_media_repair.py`
- Create: `.zcode/skills/phone-media-repair/pyproject.toml`
- Create: `.zcode/skills/phone-media-repair/phone_media_repair/__init__.py`
- Create: `.zcode/skills/phone-media-repair/SKILL.md`
- Create: `.zcode/skills/phone-media-repair/README.md`

**Acceptance Criteria:**
- [ ] `scan <dir>` (local tree) or `scan --remote` (on-phone walk of DCIM/Pictures/Movies): verdicts `intact | truncated | unknown` per media file; JSON summary printed.
- [ ] MP4/MOV verdict = ftyp box present near offset 0 AND no moov box found in the head/tail sample -> truncated; JPEG verdict = SOI marker present AND EOI marker missing at end -> truncated.
- [ ] `repair <file> --reference <good>`: untrunc binary (binfind, name-only — no winget id) when present; else ffmpeg (`Gyan.FFmpeg`) remux `-c copy` fallback; else honest guidance, exit 1.
- [ ] Repairs write NEW files (`<name>.fixed.<ext>`); originals are never overwritten or moved.
- [ ] Pure parsers decide from byte samples only: `mp4_verdict(head: bytes, tail: bytes) -> str` and `jpeg_verdict(head: bytes, tail: bytes) -> str`.
- [ ] ruff + ruff format --check + mypy --strict clean; pytest green; live scan over `data/phone-mirror` reports real verdicts without raising.

**Step 1:** Implement tool, parsers, tests, skill shim.
**Step 2:** Static checks + tests green; live mirror scan.

### Task 4: Deleted-file triage — `tools/deleted_file_triage.py`

**Dependencies:** None

**Files:**
- Create: `tools/deleted_file_triage.py`
- Test: `tools/test_deleted_file_triage.py`
- Create: `.zcode/skills/phone-triage-deleted/pyproject.toml`
- Create: `.zcode/skills/phone-triage-deleted/phone_deleted_triage/__init__.py`
- Create: `.zcode/skills/phone-triage-deleted/README.md`
- Create: `.zcode/skills/phone-triage-deleted/SKILL.md`

**Acceptance Criteria:**
- [ ] `scan` (read-only): recovery-candidate inventory — trash dirs (imports `recover_media.TRASH_DIRS`, counts files + du bytes per dir), `.thumbnails` size, `.pending`/`.trashed` overlays in DCIM; every probe degrades to "N/A", never raises.
- [ ] `deep`: root-gated extra pass; on an unrooted device prints honest requires_root guidance and exits 0 (S22+ is unrooted — verified path).
- [ ] No mutation anywhere; recommendations point at phone-recover trash (actual recovery) and data-eraser free-space (secure overwrite).
- [ ] Pure helper `triage_lines(trash_counts, thumb_bytes) -> list[str]` deterministic.
- [ ] ruff + ruff format --check + mypy --strict clean; pytest green; live scan on the S22+ green.

**Step 1:** Implement tool, tests, skill shim.
**Step 2:** Static checks + tests green; live scan on the S22+.

### Task 5: Final verification

**Dependencies:** 1, 2, 3, 4

**Files:** (none)

**Acceptance Criteria:**
- [ ] `python -m pytest tools phone-lib/tests -q -m "not device"` all green.
- [ ] Full mypy --strict CI scope (phone-lib/src diagnostics dashboard tools) clean.
- [ ] ruff check + ruff format --check clean repo-wide.
- [ ] All four console commands installed editable and answer `--help`.
- [ ] Live read-only smoke on the S22+: selective-restore `list`, migrate `plan`, media-repair `scan` (mirror), triage `scan`.
- [ ] Commit + push; CI green.

**Step 1:** Run the four static/test gates.
**Step 2:** Editable-install the four skills; live smoke; commit, push, watch CI.
