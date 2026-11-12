#!/usr/bin/env python3
"""Degradation insights from the metrics history (stdlib-only).

Analyzers are pure functions over a sqlite connection so they can run
against the live container DB (via /api/insights) or a host-side backup
copy (the daily backup is always fresh).

Usage:
    python tools/insights.py                     # analyze newest backup
    python tools/insights.py --db path/to/metrics.db
    python tools/insights.py --json              # machine-readable
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
BACKUP_DIR = REPO / "backups" / "metrics"


def _series(conn: sqlite3.Connection, expr: str, days: int) -> list[tuple[datetime, float]]:
    """(ts, value) pairs for a JSON path expression over RAW snapshots.

    The hourly rollup table only holds a rolling ~2h window (the collector
    rolls up hours_back=2 per cycle), so slopes/percentiles must come
    from raw rows.
    """
    cutoff = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)).isoformat()
    rows = conn.execute(
        "SELECT ts_utc, json_extract(device_json, ?) FROM snapshots"
        " WHERE ts_utc >= ? AND json_valid(device_json) ORDER BY ts_utc",
        (expr, cutoff),
    ).fetchall()
    out = []
    for ts, value in rows:
        try:
            out.append((datetime.fromisoformat(ts), float(value)))
        except (ValueError, TypeError):
            continue
    return out


def _slope_per_week(series: list[tuple[datetime, float]]) -> float | None:
    """Least-squares slope of value vs time, expressed per 7 days."""
    if len(series) < 3:
        return None
    t0 = series[0][0]
    xs = [(ts - t0).total_seconds() / 86400 for ts, _ in series]
    ys = [v for _, v in series]
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom == 0:
        return None
    b = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True)) / denom
    return b * 7.0


def battery_drain_rate(conn: sqlite3.Connection, days: int = 7) -> dict[str, Any]:
    """Average drain (% per hour) from raw snapshots while discharging."""
    cutoff = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)).isoformat()
    rows = conn.execute(
        "SELECT ts_utc, device_json FROM snapshots WHERE ts_utc >= ? ORDER BY ts_utc",
        (cutoff,),
    ).fetchall()
    points: list[tuple[datetime, float]] = []
    for ts, blob in rows:
        try:
            data = json.loads(blob)
            if data.get("battery", {}).get("status") == "Discharging":
                points.append((datetime.fromisoformat(ts), float(data["battery"]["level"])))
        except (ValueError, KeyError, TypeError):
            continue
    # Sampling is ~2s dense (no level change between neighbors), so pair
    # each sample with the oldest one within a 2h lookback: that spans
    # real level drops. Plausibility: >15%/h is a glitch, not a drain.
    drops = []
    j0 = 0
    for t1, l1 in points:
        while j0 < len(points) and (t1 - points[j0][0]).total_seconds() > 7200:
            j0 += 1
        if j0 < len(points) - 0 and points[j0][0] < t1:
            t0, l0 = points[j0]
            hours = (t1 - t0).total_seconds() / 3600
            per_h = (l0 - l1) / hours if hours > 0 else 0
            if hours >= 10 / 60 and 0 < per_h <= 15.0:
                drops.append(per_h)
    rate = statistics.median(drops) if drops else None
    return {
        "metric": "battery drain rate",
        "value": round(rate, 2) if rate is not None else None,
        "unit": "%/h while discharging",
        "samples": len(drops),
        "verdict": (
            "NO DATA" if rate is None else "OK" if rate < 12 else "WATCH" if rate < 20 else "ACT"
        ),
    }


def storage_growth(conn: sqlite3.Connection, days: int = 14) -> dict[str, Any]:
    """Primary partition growth per week + days until 90% full."""
    # storage[0] is the read-only root partition on Samsung - the user
    # partition is /data, found by mount_point, not by index.
    daily = _daily_means(_storage_metric(conn, "used_gb", days))
    per_week = _slope_per_week(daily)
    storage_rows = _storage_metric(conn, "total_gb", days)
    # Empty database (fresh install, no snapshots yet) must degrade to the
    # NO DATA verdict, not IndexError.
    total = storage_rows[-1][1] if storage_rows else None
    eta_days = None
    if per_week is not None and per_week > 0.01 and total:
        headroom = max(0.0, 0.9 * total - daily[-1][1])
        eta_days = round(headroom / (per_week / 7.0))
    verdict = (
        "NO DATA"
        if per_week is None
        else "OK"
        if per_week < 0.5
        else "WATCH"
        if per_week < 2.0
        else "ACT"
    )
    return {
        "metric": "storage growth (primary partition)",
        "value": round(per_week, 2) if per_week is not None else None,
        "unit": "GB/week",
        "eta_days_to_90pct": eta_days,
        "samples": len(daily),
        "verdict": verdict,
    }


def _daily_means(series: list[tuple[datetime, float]]) -> list[tuple[datetime, float]]:
    """One mean value per calendar day (drops within-day slope noise)."""
    buckets: dict[str, list[float]] = {}
    for ts, v in series:
        buckets.setdefault(ts.strftime("%Y-%m-%d"), []).append(v)
    out: list[tuple[datetime, float]] = []
    for day in sorted(buckets):
        out.append((datetime.strptime(day, "%Y-%m-%d"), statistics.mean(buckets[day])))
    return out


def _storage_metric(
    conn: sqlite3.Connection, field: str, days: int
) -> list[tuple[datetime, float]]:
    """Time series of a field from the /data entry of the storage array."""
    cutoff = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)).isoformat()
    rows = conn.execute(
        "SELECT ts_utc, json_extract(device_json, '$.storage')"
        " FROM snapshots WHERE ts_utc >= ? AND json_valid(device_json)"
        " ORDER BY ts_utc",
        (cutoff,),
    ).fetchall()
    out = []
    for ts, blob in rows:
        try:
            entry = next(part for part in json.loads(blob) if part.get("mount_point") == "/data")
            out.append((datetime.fromisoformat(ts), float(entry[field])))
        except (StopIteration, ValueError, TypeError, KeyError):
            continue
    return out


def percentile_pressure(
    conn: sqlite3.Connection, expr: str, days: int = 7, watch: float = 80.0, act: float = 92.0
) -> dict[str, Any]:
    """p95 of a percentage metric with watch/act thresholds."""
    series = _series(conn, expr, days)
    if not series:
        return {"metric": expr.strip("$."), "value": None, "verdict": "NO DATA"}
    p95 = statistics.quantiles([v for _, v in series], n=20)[-1]
    verdict = "OK" if p95 < watch else "WATCH" if p95 < act else "ACT"
    return {
        "metric": expr.strip("$."),
        "value": round(p95, 1),
        "unit": "p95",
        "samples": len(series),
        "verdict": verdict,
    }


def security_patch_age(reports_dir: Path | None = None) -> dict[str, Any]:
    """Patch-age verdict from the newest diagnostics report (nightly nag)."""
    from datetime import date

    reports_dir = reports_dir or (REPO / "diagnostics" / "reports")
    files = sorted(reports_dir.glob("health_report_*.json"))
    if not files:
        return {"metric": "security patch age", "value": None, "verdict": "NO DATA"}
    try:
        report = json.loads(files[-1].read_text(encoding="utf-8"))
        patch = report["device"]["security_patch"]
        patch_date = datetime.strptime(patch[:10], "%Y-%m-%d").date()
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return {"metric": "security patch age", "value": None, "verdict": "NO DATA"}
    days = (date.today() - patch_date).days
    # OK < 90, WATCH 90-180, ACT > 180 (aligned with config.yaml max_patch_age_days)
    verdict = "OK" if days < 90 else "WATCH" if days <= 180 else "ACT"
    return {
        "metric": "security patch age",
        "value": days,
        "unit": "days (patch " + patch[:10] + ")",
        "verdict": verdict,
    }


def analyze(conn: sqlite3.Connection) -> dict[str, Any]:
    return {
        "generated": datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z",
        "window_days": 7,
        "insights": [
            battery_drain_rate(conn),
            storage_growth(conn, days=14),
            percentile_pressure(conn, "$.memory.usage_percent"),
            percentile_pressure(conn, "$.battery.temperature_c", watch=33.0, act=38.0),
            security_patch_age(),
        ],
    }


def newest_backup() -> Path | None:
    files = sorted(BACKUP_DIR.glob("metrics-*.db"))
    return files[-1] if files else None


def format_report(report: dict[str, Any]) -> str:
    lines = [f"Insights @ {report['generated']} (window {report['window_days']}d)"]
    for item in report["insights"]:
        value = item.get("value")
        unit = item.get("unit", "")
        extra = ""
        if item.get("eta_days_to_90pct") is not None:
            extra = f", ETA to 90%: {item['eta_days_to_90pct']}d"
        if item.get("note"):
            extra += f" ({item['note']})"
        lines.append(
            f"  [{item['verdict']:>7}] {item['metric']}: "
            f"{value if value is not None else 'n/a'} {unit}{extra}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=None, help="metrics DB path (default: newest backup)")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument("--out", default=None, help="write the text report to this file")
    args = parser.parse_args(argv)

    db_path = Path(args.db) if args.db else newest_backup()
    if db_path is None or not db_path.exists():
        print(
            "no metrics DB available (run tools/backup_metrics_db.py first)",
            file=__import__("sys").stderr,
        )
        return 1
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        report = analyze(conn)
    finally:
        conn.close()
    text = json.dumps(report, indent=2) if args.json else format_report(report)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + chr(10), encoding="utf-8")
        print(f"report written to {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
