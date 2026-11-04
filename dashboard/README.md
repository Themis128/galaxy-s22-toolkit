# Galaxy S22+ Dashboard

FastAPI + WebSocket + Chart.js monitoring dashboard with an approved-repair
API and a Devin control API (API-key protected for Tailscale use).

## Run

```bash
# from the repo root
python dashboard/app.py          # http://127.0.0.1:8081
DASHBOARD_PORT=9000 python dashboard/app.py
```

Port 8080 is commonly occupied on this machine (env-manager-frontend), so
the default is 8081.

## Run in Docker

The container reaches the phone over wireless ADB through the tailnet
(enable once over USB: `adb tcpip 5555`, then the phone answers at its
Tailscale IP, port 5555):

```bash
docker compose up -d --build
```

The compose file mounts the host's ADB keys read-only so the phone does
not need to approve a new key, sets `DASHBOARD_HOST=0.0.0.0` (required
for published ports), and connects to `PHONE_ADB_HOST:5555` on start.

## Tailnet access (from the phone)

```bash
tailscale serve --bg 8081     # https://<host>.<tailnet>.ts.net -> 127.0.0.1:8081
```

On this machine the dashboard also auto-starts hidden at logon via a
Startup-folder entry (`galaxy_s22_dashboard.vbs`, no admin required),
so the phone-side URL stays available across reboots. Every scheduled
diagnostics run fires a desktop toast when it finds issues.

## Monitoring

- `GET /api/health` — current snapshot (device, battery, storage, network, thermal)
- `GET /api/history?hours=24` — time-series metrics
- `WS /ws/live` — 1s real-time updates (5s collector cadence)

## Repair API

| Endpoint | Behavior |
|---|---|
| `GET /api/repair/actions` | Recommended actions from the latest saved diagnostics report (no re-run) |
| `POST /api/repair/execute` | Runs one action. Non-auto-approve actions require `"confirm": true`, else **202 confirmation_required**. Unknown actions → 400. |
| `POST /api/repair/execute-multiple` | Same gate for any non-auto action in the batch |
| `GET /api/repair/history` | Persistent repair history (JSONL from `logs/repair_history.jsonl`) |

Every executed repair fires a desktop toast (best-effort) and is appended
to the shared repair history the CLI uses.

## Devin Control API

`/api/devin/*` requires the `X-API-Key` header (set `GROQ_BOT_API_KEY`;
optionally restrict callers with `TAILSCALE_ALLOWLIST`).

Connection profile for the bot (verified end-to-end over the tailnet):
base URL `https://office-1.tail4ecae1.ts.net` (via `tailscale serve`),
header `X-API-Key: $GROQ_BOT_API_KEY`.

| Endpoint | Purpose |
|---|---|
| `GET /api/devin/status` | Devin process + workdir status |
| `POST /api/devin/execute` | Run a shell command in the workdir (`{"command": "..."}`) |
| `GET /api/devin/files?path=.` | List workdir entries (response key: `items`) |
| `GET /api/devin/files/read?path=x` | Read a file |
| `POST /api/devin/files/write` | Write a file (`{"path": ..., "content": ...}`) |
| `DELETE /api/devin/files?path=x` | Delete a file |

All paths are confined to the Devin workdir (`DEVIN_WORKDIR`, default
`~/Devin`).

## Mobile

The UI is responsive (44px touch targets, single-column layout) for
phone access over Tailscale.
