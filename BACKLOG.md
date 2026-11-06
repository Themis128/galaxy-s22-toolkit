# Galaxy S22+ Toolkit — Issue Backlog

Reflects the state after v0.5.0 (2026-11-06).

## Open

### 1. PyPI publish still gated
The publish workflow requires `ENABLE_PYPI=true` plus the PyPI trusted-publisher record (project `galaxy-s22-toolkit`, owner `Themis128`, workflow `ci.yml`). Tag the release (v0.5.0) only after both are in place.

### 2. Phone security patch age
Run `python tools/update_check.py` (or `phone-update-check`) and apply the system update on the device; verify the patch age verdict flips to OK.

### 3. Multi-device fleet mode (not started)
The toolkit adapts to one attached Galaxy at a time. Fleet metrics schema / per-device dashboards remain out of scope until there is a second phone on the tailnet.

## Resolved (log)

- **SSRF in dashboard_client** — blocklist re-validated on every request (v0.4.0).
- **OneDrive read-only corruption** — repo relocated to `C:\dev\galaxy-s22-toolkit`; nightly pipeline verified from the new tree.
- **storage/ pytest collection errors** — legacy OneDrive placeholder dir decommissioned (`tools/decommission_legacy.py`).
- **mypy type errors** — repo-wide `--strict` clean (43 files); CI mypy widened and installs fastapi/uvicorn/types-PyYAML.
- **Pre-commit U+F03A junk-path guard** — installed and verified (core.quotePath disabled).
- **Battery "undefined mA" on dashboard** — snapshot now emits `current_ma` (sysfs fallback + µA/mA magnitude check).
- **Container ADB unreachable** — compose switched to `network_mode: host`; container shares the tailnet and connects to the phone directly.
