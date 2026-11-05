# Galaxy S22+ Toolkit - Issue Backlog

## High Priority (Blocking)

### 1. SSRF Vulnerability in `tools/dashboard_client.py`
**Status:** In Progress  
**Finding:** Mimosa security scan flagged line 50 (urllib.request.urlopen with user-controlled URL)  
**Fix:** Add URL validation to block private/internal IPs while allowing Tailscale CGNAT (100.64.0.0/10)  
**Reference:** OWASP SSRF Prevention Cheat Sheet

### 2. OneDrive Read-Only File Permission Issues
**Status:** Recurring  
**Problem:** OneDrive re-applies read-only attribute to files, blocking edits  
**Impact:** Cannot edit files without running `fix_onedrive_attrs.py` first  
**Root Cause:** OneDrive's "Files On-Demand" feature marks files as read-only  
**Mitigation:** 
- Run `fix_onedrive_attrs.py` before any edits (current workaround)
- Permanent fix: Move repo out of OneDrive with `tools/relocate_repo.py --execute`
- Pre-commit hook clears read-only on COMMIT_EDITMSG

### 3. Storage Directory Pytest Collection Errors
**Status:** Blocking full test suite  
**Errors:** 3 collection errors in `storage/` directory:
- `storage/test_insights.py` - OSError: [Errno 22] Invalid argument
- `storage/test_tools.py` - OSError: [Errno 22] Invalid argument
- `storage/tests` - OSError: [Errno 22] Invalid argument
**Cause:** Likely corrupted test files or invalid paths in OneDrive sync

## Medium Priority (Quality)

### 4. Mypy Type Errors Across Codebase
**Status:** Multiple errors  
**Files affected:**
- `tools/clean_path_artifacts.py` - Missing type annotations
- `tools/update_check.py` - Missing yaml stubs, type annotations
- `tools/alerts.py` - Cannot find `insights` module
- `dashboard/metrics_db.py` - Module name conflict, Any returns, missing type args
- `tools/doctor.py` - Cannot find local modules
- `tools/insights.py` - Untyped calls, missing annotations
- `tools/dashboard_client.py` - Missing dict type args
- `diagnostics/run_diagnostics.py` - Many type issues (yaml stubs, dict args, Optional handling)

### 5. Pre-commit Hook for OneDrive Artifacts
**Status:** Exists, needs verification  
**Hook:** `.git/hooks/pre-commit` checks for U+F03A () mangled paths  
**Script:** `tools/install_git_hooks.py` installs it  
**Need:** Verify it catches the junk files correctly

### 6. PyPI Publishing Configuration
**Status:** Gated behind `ENABLE_PYPI` variable  
**Required:** 
1. Configure trusted publisher on pypi.org (project: `galaxy-s22-toolkit`, owner: `Themis128`, repo: `galaxy-s22-toolkit`, workflow: `ci.yml`)
2. Set GitHub Actions variable `ENABLE_PYPI=true`
3. Tag new version (v0.3.1+) and push

## Low Priority (Operational)

### 7. Phone Security Update
**Status:** 91 days overdue  
**Action:** Run `python tools/update_check.py --open-settings` on device

### 8. Repository Relocation from OneDrive
**Status:** Optional but recommended  
**Tool:** `python tools/relocate_repo.py --execute`  
**Post-move:** Reinstall phone-lib, rebuild docker, re-register tasks

---

## Resolution Log

### ✅ Completed: Patch Age Threshold Alignment (585fcd9)
- Changed OK/WATCH/ACT boundaries from 60/90 to 90/180 days
- Updated: `tools/insights.py`, `dashboard/app.py`, `diagnostics/config.yaml`, `tools/test_tools.py`
- All 207 tests pass (--ignore=storage)