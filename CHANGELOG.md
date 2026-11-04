# Changelog

All notable changes to the Galaxy S22+ toolkit. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); dates are ISO 8601.

## [0.3.0] - 2026-11-04

### Fixed
- **Android 16 network detection** (all live-verified on SM-S906B): default
  gateway now falls back to per-network route tables; internet probe appends
  `&& echo connected` (toybox `nc -z` is silent on success); DNS falls back
  to `ping` (`nslookup` no longer exists on Android 16); toybox `ping -W`
  is seconds, not milliseconds.
- Battery: instantaneous current and charge counter parsed from
  `dumpsys battery` (previously always N/A via a dead property).
- Storage diagnostics: immutable factory partitions (`/`, `/vendor`,
  `/apex/*`, ...) no longer trip the usage/free-space thresholds;
  `/cache` excluded from the <2 GB check (512 MB by design).
- Dashboard: `/api/devin/*` degrade to 503 when the Devin CLI/tools are
  missing (e.g. in Docker) instead of raw 500s; `/api/health` also handles
  a missing adb binary (OSError → 503).
- Docker: dashboard `dashboard.metrics_db` import crash fixed (repo root on
  sys.path); metrics history now persists in the named volume `metrics-data`
  (survives rebuilds and `compose down`).
- CI: `-k "not device"` silently skipped all of `test_device.py` — replaced
  with marker-based `-m "not device"`; root `ruff.toml` pins the rule set
  against ruff 0.17's expanded defaults; `.gitattributes` pins LF.
- Pre-commit hook: U+F03A junk-path guard now disables `core.quotePath`
  (git's path quoting previously made the guard a no-op); installer clears
  the read-only flag OneDrive re-applies to the hook.

### Added
- **Test suites**: dashboard (20 tests), device integration (7, marker-gated,
  read-only against the live phone), tools (10) — 196 total unit tests.
- **tools/**: `backup_metrics_db.py` (consistent snapshot out of the Docker
  volume + `--restore` with WAL-sidecar handling, drill-verified),
  `fix_onedrive_attrs.py`, `clean_path_artifacts.py`,
  `install_git_hooks.py`, `doctor.py` (environment health incl. backup
  freshness), `update_check.py` (security-patch age verdict; can open the
  system update screen).
- **Insights & alerting foundation**: `tools/insights.py` + `/api/insights`
  + dashboard_client `insights` - battery drain rate (median %/h,
  glitch-filtered), storage growth GB/week on /data with ETA to 90%
  (needs 3+ days history), memory/thermal p95 with OK/WATCH/ACT
  verdicts. Skill: `phone-insights`.
- **Skills**: `phone-update-check`, `phone-doctor`, `phone-connect`
  (wireless ADB status/connect/reconnect), `phone-remote-control`
  (dashboard REST API client; the Groq bot's client-side contract).
- **tools/**: `adb_connect.py` (live-verified: auto re-established a
  dropped Wi-Fi transport), `dashboard_client.py` (stdlib-only; verified
  on localhost and the tailnet URL; refuses repairs without --confirm).
- CI: dashboard test step; Windows runners with uv; wheel build; PyPI
  trusted publishing on release.

## [0.2.0] - 2026-11-04

- Historical metrics persistence (SQLite, hourly/daily rollups, 10-day
  retention) with 5 trend API endpoints and dashboard trend charts.
- Repair layer: 14 actions, toast approvals, JSONL history, dashboard
  confirm gate; 11/11 E2E.
- Installer E2E 8/8; silent scheduled task; wireless ADB auto-reconnect;
  Dockerized dashboard on tailnet; phone-repair skill; Groq bot API profile.

## [0.1.0] - 2026-11-03

- Initial release: phone-lib (typed async ADB wrapper), diagnostics runner,
  6 ZCode skills, FastAPI dashboard, installer.
