#!/usr/bin/env python3
"""Alert evaluation over the toolkit's insight data (stdlib-only).

Pure evaluator: maps insight verdicts to actionable alerts. Used by the
dashboard /api/alerts endpoint (in-container, live DB) and the host CLI
(newest backup DB + newest diagnostics report).

Usage:
    python tools/alerts.py                  # evaluate newest backup
    python tools/alerts.py --json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
from insights import analyze, newest_backup, security_patch_age  # noqa: E402

SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2}


def evaluate(insights: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map non-OK insight verdicts to alerts (stateless, dedup by id)."""
    alerts: list[dict[str, Any]] = []
    for item in insights:
        verdict = item.get("verdict")
        if verdict not in ("WATCH", "ACT"):
            continue
        if item.get("value") is None:
            continue
        metric = item.get("metric", "unknown")
        unit = item.get("unit", "")
        value = item.get("value")
        eta = item.get("eta_days_to_90pct")
        message = f"{metric}: {value} {unit}".strip()
        if eta is not None:
            message += f" - full in ~{eta} days"
        alerts.append(
            {
                "id": metric,
                "severity": "critical" if verdict == "ACT" else "warning",
                "source": "insights",
                "message": message,
                "recommendation": _recommendation(metric),
            }
        )
    return alerts


def _recommendation(metric: str) -> str:
    if "drain" in metric:
        return (
            "Check for rogue apps (Settings > Battery > Background usage); "
            "consider phone-repair force_stop_misbehaving_apps"
        )
    if "storage" in metric:
        return "Run phone-repair clear_app_caches / remove_temp_files"
    if "memory" in metric:
        return "Restart the device; check running apps via phone-app-manager"
    if "temperature" in metric:
        return "Remove the case / stop charging; check thermal via diagnostics"
    if "patch" in metric:
        return "Settings > Software update > Download and install"
    return "Run python tools/doctor.py for a full environment check"


def collect_host() -> tuple[list[dict[str, Any]], int]:
    """Host-side: insights from newest backup + patch age from reports."""
    db_path = newest_backup()
    if db_path is None:
        return [], -1
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        report = analyze(conn)
    finally:
        conn.close()
    insights = report["insights"]
    # replace the container's NO-DATA patch entry with the host-side one
    insights = [i for i in insights if "patch" not in i.get("metric", "")]
    insights.append(security_patch_age())
    return insights, 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    insights, _ = collect_host()
    alerts = evaluate(insights)
    if args.json:
        print(json.dumps({"alerts": alerts}, indent=2))
    elif alerts:
        for a in sorted(alerts, key=lambda x: -SEVERITY_ORDER[x["severity"]]):
            print(f"[{a['severity'].upper():>8}] {a['message']}")
            print(f"           -> {a['recommendation']}")
    else:
        print("no active alerts")
    return 1 if any(a["severity"] == "critical" for a in alerts) else 0


if __name__ == "__main__":
    raise SystemExit(main())
