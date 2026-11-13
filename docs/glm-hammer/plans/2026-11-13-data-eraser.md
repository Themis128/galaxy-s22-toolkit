# Blueprint plan — Data Eraser (prepare-to-sell), 2026-11-13

Adopts Wondershare "Data Eraser": a safe erase flow for selling or giving
away the phone. Non-root, honest about flash reality (free-space overwrite
is best-effort on FBE flash; remnants of deleted files in app data dirs,
thumbnails, and DB freelists are the realistic target — per-file encryption
already protects most content). Mirrors `tools/repair_system.py` conventions
(config-loaded client via `phone.create_client`, typed gates, hermetic
pure-function tests in `tools/test_*.py`).

## Task 1: `tools/data_eraser.py` — erase CLI

**Dependencies:** None

**Files:**
- Create: `tools/data_eraser.py`

**Acceptance Criteria:**

- [ ] CLI with subcommands `status`, `free-space`, `reset`, `certificate`
      (`python tools/data_eraser.py <cmd>`); `--serial` on all subcommands;
      docstring states the flash-encryption honesty note verbatim:
      "Free-space overwrite is best-effort on encrypted flash; per-file FBE
      keys already protect deleted content — this pass covers remnants in
      shared storage trees, thumbnails, and database freelists."
- [ ] `status` (read-only): prints device identity (model/serial/Android),
      `ro.crypto.state`, FRP partition (`ro.frp.pst`), storage usage,
      installed-app count, media counts for `/sdcard/DCIM`, `/sdcard/Pictures`,
      `/sdcard/Download`, WhatsApp DB presence, and a "what will be lost"
      checklist; every probe degrades to "N/A" on error, never raises.
- [ ] `free-space`: requires `--yes`; writes random-filled files into
      `/sdcard/erase-fill-<ts>/` (shell-writable shared storage) until free
      space on `/sdcard` < 64 MB or 5 files created, fsyncs, deletes the
      directory, reports bytes written and df before/after; appends one
      action line to the certificate JSONL.
- [ ] `reset`: without `--execute` prints the exact Settings path guidance
      and exits 0; with `--execute` requires a typed `ERASE-PHONE` confirm,
      then runs
      `am broadcast -a android.intent.action.MASTER_CLEAR`, appends the
      action to the certificate JSONL, and never runs when the typed
      confirm does not match exactly.
- [ ] `certificate`: renders the erase certificate JSON for the serial from
      the action JSONL at `data/erase-certificates/<serial>.jsonl`
      (device identity, action list with timestamps and outcomes, honesty
      note); `--show` prints it; no flag writes it to
      `data/erase-certificates/<serial>-<timestamp>.json`.
- [ ] Pure helpers separated and importable without a device:
      `parse_df`, `parse_app_count`, `build_certificate`,
      `confirm_typed`; module importable without `phone` installed
      (`create_client` import guarded exactly like `repair_system.py`).
- [ ] `ruff check` + `ruff format --check` + `mypy --strict` clean on the
      new file.

**Step 1:** Create `tools/data_eraser.py` with the four subcommands, the
typed confirm gate (`confirm_typed(prompt, expected, input_fn)`), the
certificate JSONL append/read helpers, and the pure parsers
(`parse_df`, `parse_app_count`, `build_certificate`).

**Step 2:** Verify `python -m ruff check`, `ruff format`, and
`mypy tools/data_eraser.py --strict --explicit-package-bases` are clean.

## Task 2: `tools/test_data_eraser.py` — hermetic tests

**Dependencies:** Task 1

**Files:**
- Test: `tools/test_data_eraser.py`

**Acceptance Criteria:**

- [ ] Tests import the module hermetically (`ROOT = Path(__file__).resolve().parents[1]`,
      `sys.path.insert(0, str(ROOT))`) without any device or adb present.
- [ ] `parse_df` parses a real `dumpsys df` fragment into
      `(used_gb, free_gb)` for the `/data` or `/storage/emulated` row,
      returns `None` on empty/garbage input.
- [ ] `parse_app_count` extracts the count from `pm list packages` output
      and returns `None` on empty output.
- [ ] `build_certificate` returns a dict with keys `device`, `actions`,
      `honesty_note`, `generated` and `actions` entries carry
      `action`, `timestamp`, `outcome`.
- [ ] `confirm_typed` with a stub `input_fn`: exact `ERASE-PHONE` returns
      True; wrong text returns False and re-prompts once; EOF/empty returns
      False without raising.
- [ ] CLI gate behavior: `reset` without `--execute` exits 0 with guidance
      (monkeypatched client), and `free-space` without `--yes` exits
      non-zero without calling the client.
- [ ] `python -m pytest tools/test_data_eraser.py -q` passes, and
      `ruff check`/`ruff format --check`/`mypy --strict` stay clean on the
      test file.

**Step 1:** Create `tools/test_data_eraser.py` covering the six criteria
above with fake clients (simple objects with `execute` methods).

**Step 2:** Run `python -m pytest tools/test_data_eraser.py -q`;
all green.

## Task 3: Final verification

**Dependencies:** Task 2

**Files:** (none)

**Acceptance Criteria:**

- [ ] `python -m pytest tools/ -q` passes with the new tests included.
- [ ] `ruff check tools` and `ruff format --check tools` clean.
- [ ] `mypy tools/data_eraser.py tools/test_data_eraser.py --strict
      --explicit-package-bases` clean.
- [ ] Live smoke on the attached S22+ (device marker respected:
      `pytest -m device` untouched): `python tools/data_eraser.py status`
      runs against the real phone and prints the inventory without raising.

**Step 1:** Run the three static/test commands; all green.

**Step 2:** Run `python tools/data_eraser.py status` against the attached
phone; inventory prints, no exception.
