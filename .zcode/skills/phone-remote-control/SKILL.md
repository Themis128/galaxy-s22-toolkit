---
name: phone-remote-control
description: Query and control the Galaxy S22+ through the dashboard REST API from anywhere on the tailnet
version: 1.0.0
author: Galaxy S22+ Toolkit
tags:
  - dashboard
  - remote
  - tailnet
  - api
  - repairs
---

# Phone Remote Control

CLI client for the dashboard REST API - the same interface the Groq bot
uses. Works from any tailnet device against the deployed container.

## Usage

```bash
python tools/dashboard_client.py health
python tools/dashboard_client.py trends battery.level --period stats
python tools/dashboard_client.py metrics
python tools/dashboard_client.py repair-actions
python tools/dashboard_client.py repair-history
python tools/dashboard_client.py diagnose              # triggers a run
python tools/dashboard_client.py alerts                # active alerts
python tools/dashboard_client.py repair clear_app_caches --confirm
```

## Remote access

```bash
python tools/dashboard_client.py --base-url http://100.83.120.93:8081 health
```

## Safety

- Mutating repairs require `--confirm` (exit 2 otherwise), mirroring the
  server-side approval policy.
- Auth is the X-API-Key from `.env` (GROQ_BOT_API_KEY); give the same
  value to the bot side. Endpoints return 401 without it.
