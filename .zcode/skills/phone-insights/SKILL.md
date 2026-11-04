---
name: phone-insights
description: Degradation insights from metrics history - battery drain rate, storage growth ETA, memory and thermal pressure
version: 1.0.0
author: Galaxy S22+ Toolkit
tags:
  - analytics
  - battery
  - storage
  - trends
---

# Phone Insights

Turns the accumulated metrics history into degradation verdicts
(OK / WATCH / ACT / NO DATA). Analyzers read raw snapshots - the
hourly rollup table only holds a rolling ~2h window.

## Usage

```bash
python tools/insights.py            # analyze newest backup DB
python tools/insights.py --json     # machine-readable
python tools/dashboard_client.py insights   # live via the dashboard API
```

## Insights

1. battery drain rate - median %/h while discharging (10min-2h lookback
   pairing; >15%/h treated as a glitch)
2. storage growth - GB/week on /data (found by mount point, not index)
   + ETA to 90% full (needs >=3 days of history)
3. memory usage p95
4. battery temperature p95

Verdicts become meaningful as history accumulates - storage growth
reports NO DATA until ~3 days are collected.
