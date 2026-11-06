# Galaxy S22+ Dashboard

FastAPI + WebSocket + Chart.js monitoring dashboard with the approved-repair API, root/Magisk module management, insights/alerts/trends APIs, and a Devin control API (API-key protected for Tailscale use).

**Live deployment**: host-network container at `http://100.83.120.93:8081` — reachable from any browser on the tailnet, including the ZCode integrated browser. CORS is allow-all for that purpose.

## Run

```bash
python dashboard/app.py          # http://127.0.0.1:8081
DASHBOARD_PORT=9000 python dashboard/app.py
```

Port 8080 is commonly occupied on this machine (env-manager-frontend), so the default is 8081.

## Run in Docker

The container runs with `network_mode: host`, shares the host's tailnet, and reaches the phone over wireless ADB (enable once over USB: `adb tcpip 5555`, then the phone answers at its Tailscale IP, port 5555):


The compose file mounts the host's ADB keys read-only so the phone does not need to approve a new key, sets `DASHBOARD_HOST=0.0.0.0`, and runs `adb connect $PHONE_ADB_HOST:5555` at start. Metrics persist in the named volume `metrics-data`.

## Tailnet access (from the phone)

```bash
tailscale serve --bg 8081     # https://<host>.<tailnet>.ts.net -> 127.0.0.1:8081
```

On this machine the dashboard also auto-starts hidden at logon via a Startup-folder entry (`galaxy_s22_dashboard.vbs`, no admin required), so the phone-side URL stays available across reboots. Every scheduled diagnostics run fires a desktop toast when it finds issues.

## Monitoring

- `GET /api/health` — current snapshot: device, **device_profile** (marketing name/series/chipset/One UI), battery incl. `current_ma`, storage, network, thermal, cpu, memory, apps, full root state
- `GET /api/history?hours=24` — in-memory time-series
- `WS /ws/live` — `initial` snapshot, then `metrics` broadcasts **every 5 s**
- `GET /api/trends/*`, `/api/alerts`, `/api/insights` — SQLite-persisted rollups (10-day retention), verdict-based alerting from history
- `GET /alerts` — human-readable alert board page

## Repair API

| Endpoint | Behavior |
|---|---|
| `GET /api/repair/actions` | Recommended actions from the latest saved diagnostics report (no re-run) |
| `POST /api/repair/execute` | Runs one action. Non-auto-approve actions require `"confirm": true`, else **202 confirmation_required**. Unknown actions → 400. |
| `POST /api/repair/execute-multiple` | Same gate for any non-auto action in the batch |
| `GET /api/repair/history` | Persistent repair history (JSONL from `logs/repair_history.jsonl`) |

Every executed repair fires a desktop toast (best-effort) and is appended to the shared repair history the CLI uses.

## Root / Magisk API

| Endpoint | Behavior |
|---|---|
| `GET /api/root` | Full root state: `rooted`, `su_path`, `magisk_version`, `denylist_enabled`, `modules_dir_present`, `knox_status` |
| `GET /api/root/modules` | Installed Magisk modules ({id, disabled, pending_removal}), empty pre-root |
| `POST /api/root/modules/{id}/{action}` | action = enable|disable|remove. Requires "confirm": true, else 202 confirmation_required. Invalid module id: 400. su failure: 500 with the error. |

Module changes are marker files under `/data/adb/modules/<id>/` — they take effect at the next boot. Module ids are whitelisted (`^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`) so no shell metacharacters or path traversal can reach the su command line. Knox status is readable pre-root (`intact` / `tripped` / `unknown`).

## Devin Control API

`/api/devin/*` requires the `X-API-Key` header (set `GROQ_BOT_API_KEY`; optionally restrict callers with `TAILSCALE_ALLOWLIST`).

Connection profile for the bot (verified end-to-end over the tailnet): base URL `https://office-1.tail4ecae1.ts.net` (via `tailscale serve`), header `X-API-Key: $GROQ_BOT_API_KEY`.

| Endpoint | Purpose |
|---|---|
| `GET /api/devin/status` | Devin process + workdir status |
| `POST /api/devin/execute` | Run a shell command in the workdir |
| `GET /api/devin/files?path=.` | List workdir entries (response key: items) |
| `GET /api/devin/files/read?path=x` | Read a file (max 1 MB) |
| `POST /api/devin/files/write` | Write a file |
| `DELETE /api/devin/files?path=x` | Delete a file |
| `GET /api/devin/logs` | Tail the newest workdir log |

All paths are confined to the Devin workdir (`DEVIN_WORKDIR`, default ~/Devin).

## Mobile

The UI is responsive (44px touch targets, single-column layout) for phone access over Tailscale.
