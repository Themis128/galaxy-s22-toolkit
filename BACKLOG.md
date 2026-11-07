# Galaxy S22+ Toolkit — Issue Backlog

Reflects the state after v0.5.0 published (2026-11-07).

## Open

### 1. Phone security patch install
Patch 2026-08-05 (94 days, OUTDATED). The update-check broadcast was fired over ADB; the install itself requires the device **unlocked** (Settings → Software update → Download and install). The alert self-clears once installed.

### 2. Legacy OneDrive tree retirement — 95% DONE (2026-11-07)
Executed: 8.3 GB of phone-mirror data moved to `data/legacy-mirror/`, personal files archived to `data/legacy-archive/`, 57 cloud-only WhatsApp-backup placeholders documented in `data/legacy-archive/SKIPPED-CLOUD-FILES.txt` (their cloud copies survive in OneDrive), the tree itself deleted down to the harness dirs `.zcode/.mimosa/.glm-hammer` (2.4 MB). **Remaining**: after this session ends, run from a fresh terminal `python tools\retire_legacy_tree.py --execute --all` to remove the last harness state (the tool handles read-only re-flagging and cloud placeholders; resumable).

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
