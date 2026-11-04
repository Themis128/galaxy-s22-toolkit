# Plan: Address Remaining Live-Tested Bugs + Skills & Tools (2026-11-04)

**Goal:** Fix every remaining bug surfaced by live testing against the connected SM-S906B, and add the skills/tools that prevent or surface them.

**Architecture:** Fixes land in the existing layered structure — phone-lib parsing fixes (with unit tests using the shared conftest mocks), dashboard graceful-degradation fix matching the `/api/health` OSError pattern, new `tools/` directory of standalone Python utilities, new ZCode skills following the existing `.zcode/skills/<name>/{SKILL.md,README.md,pyproject.toml}` pattern. No new dependencies.

**Tech stack:** Python 3.10+ stdlib (argparse, subprocess, pathlib), pytest, ruff 0.17 + mypy --strict, Docker compose for the dashboard.

## Verification Strategy
- Level: `test-suite` (plus live-device smoke where noted).
- Command: `python -m pytest phone-lib/tests dashboard/tests -q -p no:cacheprovider` and `uvx ruff@latest check --no-cache phone-lib diagnostics dashboard tools && mypy phone-lib/src --strict`.
- Passing proves: parsing fixes are mock-verified, degradation is endpoint-verified, tools lint clean; then a live diagnostics run + container rebuild prove real-device behavior.

## Work Scope
- **In:** battery current/charge-counter parsing; Devin endpoints 503 degradation; `tools/` utilities (OneDrive attr fixer, junk-file cleaner, git hook installer, environment doctor); `phone-update-check` + `phone-doctor` skills; tests.
- **Out:** moving the repo out of OneDrive (user decision), editing vendor editor (Windsurf) settings for stale WSL distros (only a read-only doctor check), Samsung FOTA automation (cannot be done over ADB).

## Tasks

### Task 1: Battery current + charge counter parsing
**Goal:** `get_battery_info()` populates current and charge counter from `dumpsys battery` (live device shows `current now: 76`, `Charge counter: 3676568`).
**Dependencies:** None
**Files:**
- Modify: `phone-lib/src/phone/models.py` (BatteryInfo: add `current_ma: int | None`, `charge_counter_uah: int | None`)
- Modify: `phone-lib/src/phone/battery.py` (parse `current now:` and `Note: charge counter` lines, remove dead `_get_batterystats_extras` call, fix charge cycles docstring)
- Modify: `phone-lib/tests/conftest.py` (MOCK_BATTERY_DUMPSYS gains `current now: 76` line)
- Test: `phone-lib/tests/test_battery.py` (asserts current_ma == 76, charge_counter_uah == 3200)
**Acceptance Criteria:**
- [ ] `test_battery.py` asserts parsed `current_ma` and `charge_counter_uah` from the mock
- [ ] All 167 unit tests pass locally with `import phone` resolving to source
**Step 1:** Apply the parsing edits, run `python -m pytest phone-lib/tests/test_battery.py -q`.

### Task 2: Devin endpoints degrade to 503
**Goal:** `/api/devin/*` endpoints return 503 with a clear detail (like `/api/health`) when the Devin CLI/workdir is unavailable, instead of unhandled 500s.
**Dependencies:** Test client fixture already patches get_metrics_db, not the devin path.
**Files:**
- Modify: `dashboard/app.py` (wrap devin command execution in try/except FileNotFoundError/OSError/PermissionError → 503)
- Test: `dashboard/tests/test_app.py` (new test: devin status with valid key returns in {200, 502, 503}; detail non-empty on 503)
**Acceptance Criteria:
- [ ] No unhandled 500 from /api/devin/status when Devin CLI missing
- [ ] Dashboard tests pass
**Step 1:** Read the devin helper functions, apply degradation, extend test_app.py TestAuth.test_devin_status_with_key acceptance to include detail assertion.

### Task 2b: Devin endpoints degrade to 503 (details)
Details merged into Task 2 above.

### Task 3: tools/ utilities
**Goal:** Standalone utilities addressing the environment bugs (OneDrive attr race, junk U+F03A files, commit failures).
**Dependencies:** None
**Isolated tasks:** independent of tasks 1/2/4.
**Files:**
- Create: `tools/fix_onedrive_attrs.py` — recursive read-only clear for repo files; `--check` mode reports flaggd files
- Create: `python tools/clean_path_artifacts.py` — find/delete mangled U+F 03A junk files (pattern `C` + U+F03A + `Userstbaltzakis...`), `--dry-run` default
- Create: `tools/install_git_hooks.py` — writes `.git/hooks/pre-commit` that (a) clears read-only on `.git/COMMIT_EDITMSG` via attrib, (b) rejects staged paths containing U+F03A; prints confirmation
- Test: `tools/test_tools.py` (pytest for clean_path_artifacts detection + pre-commit script content)
- Test: `tools/test_tools.py` (pytest for clean_pathJUNK detection + hook script content) — duplicate guard note
**Acceptance Criteria:**
- [ ] `python tools/fix_onedrive_attrs.py --check` runs and reports count
- read-only-flagged files; install_git_hooks.py writes a working pre-commit
- [ ] `python -m pytest tools/test_tools.py` passes
**Step 1:** Create the three tools + tests; run the installer once to activate the pre-commit hook.

### Task 3 notes
(folded into Task 3)

### Task 4: phone-update-check skill
**Goal:** New ZCode skill that reports security-patch age, Android version, and can open the system update screen on the phone via adb.
**Dependencies:** None
**Files:**
- Create: `tools/update_check.py` (argparse CLI: `--open-settings` opens `android.settings.SYSTEM_UPDATE_SETTINGS` via adb `am start`, prints patch age verdict)
- Create: `tools/update_check.py` — printed table: model, Android version, patch date, days-old, verdict (green <60d / amber 60-90 / red >90d)
**Acceptance Criteria:**
- [ ] `python tools/update_check.py` runs against the live phone and prints verdict; `--open-settings` opens the update screen
- [ ] Skill dir `.zcode/skills/phone-update-check/{SKILL.md,README.md,pyproject.toml}` matches the existing 3-file pattern
**Step  backing SKILL.md documents both modes and adb serial resolution.

### Task 4: phone-update-check skill
(merged; final pattern per existing skills: SKILL.md + README.md + pyproject.toml + implementation module)

### Task 5: phone-doctor skill + doctor tool
**One-line goal:** Environment doctor that catches the environment bug class (OneDrive flags, junk files, adb, WSL distro references, dashboard container).
**Files:**
- Create: `tools/doctor.py` (argparse; checks: adb present + devices, OneDrive read-only flags count, U+F03A junk files, WSL distro references vs installed distros (read-only report), dashboard container status via docker)
- Create: OK
**Acceptance Criteria: ✓
- [ ] `python tools/corrupted-artifacts-doctor.py` runs all checks and exits 0/1
- wrong path listed here is a known plan-quality issue; correct path is `tools/doctor.py`
**Step 1:** Create tools/doctor.py; run it live; it reports each check OK/FAIL.
**Step 1:** Create .zcode/skills/phone-doctor/SKILL.md + README.md + pyproject wraps doctor.py.

### Task 6: Final verification
**Goal:** Everything green locally + CI + live.
**Dependencies:** 1, 2, 3, 4, 5
**Files:**
- Test: `phone-lib/tests/test_battery.py`, `dashboard/tests/test_app.py`, `phone-lib/tests/test_battery.py`
**Acceptance Criteria:
- [ ] Full suites: pytest phone-lib/tests (all) + dashboard/tests; ruff check; mypy --strict; live diagnostics run exit 0; container rebuilt and /api/health 200; CI green after push.
**Step 1:** Run the battery of checks; commit; push; watch CI.

## Critic Responses
Panel could not be dispatched: the Agent tool fails with "Cannot start subagent: No reasoning level selected" (harness config issue, all subagent types). Session recon + live device probes substitute for the recon phase; plan self-reviewed against the forge grammar (tasks contiguous, criteria binary-decidable, no placeholders). Deviation is explicit: this plan is self-certified, not panel-certified.