# Galaxy S22+ Toolkit — Issue Backlog

Reflects the state after v0.5.0 published (2026-11-07).

## Open

### 1. Phone security patch install
Patch 2026-08-05 (94 days, OUTDATED). The update-check broadcast was fired over ADB; the install itself requires the device **unlocked** (Settings → Software update → Download and install). The alert self-clears once installed.

### 2. Legacy OneDrive tree retirement (one command)
The old tree at `CrossDevice\Galaxy S22+ (2)` holds 8.9 GB of phone-mirror data and divergent git history. `python tools/retire_legacy_tree.py` (dry-run) verifies the canonical repo is clean+pushed, inventories everything, moves `data/` into the canonical `data/legacy-mirror/` (same-volume rename) and preserves the stray personal files. Run `--execute` **from a directory outside the legacy tree** (keeps `.zcode`/`.mimosa`/`.glm-hammer` for any attached session); add `--all` from a fresh terminal later.

### 3. Multi-device fleet mode (deferred by design)
The toolkit adapts to one attached Galaxy at a time; per-device dashboards stay out of scope until a second phone exists on the tailnet.

## Resolved (log)

- **PyPI publish: DONE** — v0.5.0 is live on PyPI (trusted publishing verified end-to-end: tag → release → Build Wheel → Publish to PyPI → pypi.org/pypi/galaxy-s22-toolkit). `pip install galaxy-s22-toolkit` gets 0.5.0.
- **SSRF in dashboard_client** — blocklist re-validated on every request (v0.4.0).
- **OneDrive read-only corruption** — repo relocated to `C:\dev\galaxy-s22-toolkit`.
- **storage/ pytest collection errors** — legacy placeholder dir decommissioned.
- **mypy type errors** — repo-wide `--strict` clean.
- **Battery "undefined mA" / Running Apps 0 / DNS N/A / status badge CRITICAL** — Android 16 fallbacks + field fixes (v0.5.0).
- **Container ADB unreachable / history split** — bridge+LAN-IP compose; shared repair history bind mount.
