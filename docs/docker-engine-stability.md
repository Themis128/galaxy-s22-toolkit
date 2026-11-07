# Docker Engine Stability on this machine

The Docker Desktop engine crashed 4× on 2026-11-07 (WSL `E_UNEXPECTED`,
engine-pipe EOF, "WSL integration unexpectedly stopped"). Root-cause chain
and the permanent mitigations, so the next occurrence is a non-event.

## Mechanism

- Windows Insider build 26340 + WSL 3.0.5 + `autoMemoryReclaim=dropCache`
  (a setting 2025 web/GitHub research reports as VM-crash-prone).
- Event log shows Hyper-V VmSwitch reloads (driver load + RSC offload
  changes ×4) at each crash — every NIC event (phone USB plug/unplug,
  Tailscale adapter churn) rebuilds the switch under the WSL VM.
- When the VM dies, the engine pipe EOFs and every browser tab on the
  dashboard spam-logs WS reconnect failures until recovery.

## Mitigations applied (2026-11-07)

1. **`.wslconfig`: `autoMemoryReclaim=dropCache` → `gradual`** (backup:
   `.wslconfig.bak-20261107-stability`). The host-starvation problem that
   motivated dropCache is solved at the source by the 2026-11-06
   CommitLimit fix (`memory=12GB` + `swap=24GB` → CommitLimit 30 GB vs
   observed Committed_AS peak 26.3 GB). Research: dropCache crashes the VM
   itself (microsoft/WSL#8725 et al.). Applied via `wsl --shutdown` +
   Docker Desktop restart.
2. **`wsl --update`** — WSL 3.0.5.0 already current.
3. **Watchdog (permanent self-healing)**: `tools/docker_watchdog.py` +
   scheduled task **`\Docker Engine Watchdog`** (every 15 min, pythonw,
   no window). Probes the engine pipe; if down → starts Docker Desktop →
   waits ≤3 min → `docker compose up -d`; if the engine is up but the
   dashboard container is not → composes up. Logs to
   `logs/docker-watchdog.log` (1 MB cap). Live-fire verified both paths.

## If it still crashes

- The watchdog heals within ≤15 min without human action; the browser tab
  self-reconnects (WS backoff) once the engine returns.
- Escalation order from the research: `wsl --shutdown` + Docker restart →
  `wsl --update` → check Hyper-V/Virtual Machine Platform features →
  re-register the docker-desktop distro (⚠ wipes Docker data — back up
  `metrics-data` first) → pause Insider Dev channel builds → clean
  Docker Desktop reinstall.
