"""Tests for tools/insights.py analyzers (synthetic data, no hardware)."""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.insights import (  # noqa: E402
    _daily_means,
    _slope_per_week,
    battery_drain_rate,
    percentile_pressure,
    storage_growth,
)


def _base(days_ago: float) -> datetime:
    """UTC-naive timestamp `days_ago` before now — DB analyzers filter by
    a rolling window, so hardcoded dates decay into NO DATA over time."""
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_ago)


def _seed_db(tmp_path: Path, snapshots: list[tuple[str, str]]) -> sqlite3.Connection:
    db = tmp_path / "metrics.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE snapshots (id INTEGER PRIMARY KEY, ts_utc TEXT, device_json TEXT)")
    for ts, payload in snapshots:
        conn.execute(
            "INSERT INTO snapshots (ts_utc, device_json) VALUES (?, ?)",
            (ts, payload),
        )
    conn.commit()
    return conn


def _snap(
    ts: datetime,
    level: float,
    status: str = "Discharging",
    used_gb: float = 100.0,
    total_gb: float = 225.0,
) -> tuple[str, str]:
    return (
        ts.isoformat(),
        json_dumps(level, status, used_gb, total_gb),
    )


def json_dumps(level: float, status: str, used_gb: float, total_gb: float) -> str:
    storage = [
        {"mount_point": "/", "used_gb": 6.0, "total_gb": 6.0},
        {"mount_point": "/data", "used_gb": used_gb, "total_gb": total_gb},
    ]
    import json

    return json.dumps(
        {
            "battery": {"level": level, "status": status, "temperature_c": 30.0},
            "memory": {"usage_percent": 50.0},
            "storage": storage,
        }
    )


class TestSlope:
    def test_flat_series_is_zero(self) -> None:
        t0 = datetime(2026, 11, 1)
        series = [(t0 + timedelta(days=i), 100.0) for i in range(5)]
        assert _slope_per_week(series) == 0.0

    def test_growth_of_1gb_per_day_is_7_per_week(self) -> None:
        t0 = datetime(2026, 11, 1)
        series = [(t0 + timedelta(days=i), 100.0 + i) for i in range(5)]
        slope = _slope_per_week(series)
        assert slope is not None
        assert abs(slope - 7.0) < 1e-9

    def test_too_few_points_is_none(self) -> None:
        t0 = datetime(2026, 11, 1)
        assert _slope_per_week([(t0, 1.0), (t0 + timedelta(days=1), 2.0)]) is None


class TestDailyMeans:
    def test_buckets_by_day(self) -> None:
        t0 = datetime(2026, 11, 1, 10, 0)
        series = [(t0, 1.0), (t0 + timedelta(hours=1), 3.0), (t0 + timedelta(days=1), 5.0)]
        daily = _daily_means(series)
        assert len(daily) == 2
        assert daily[0][1] == 2.0
        assert daily[1][1] == 5.0


class TestBatteryDrain:
    def test_median_drain_from_lookback_pairs(self, tmp_path: Path) -> None:
        base = _base(2)
        snaps = []
        # Discharging at 10%/h, sampled every 30 min (the analyzer treats
        # >15%/h as a glitch, so the synthetic drain must stay under it)
        for i in range(5):
            ts = base + timedelta(minutes=30 * i)
            snaps.append(_snap(ts, 90.0 - 5.0 * i))
        conn = _seed_db(tmp_path, snaps)
        result = battery_drain_rate(conn, days=7)
        assert result["value"] is not None
        assert 9.0 < result["value"] <= 11.0
        assert result["verdict"] == "OK"

    def test_charging_samples_excluded(self, tmp_path: Path) -> None:
        base = _base(2)
        snaps = []
        for i in range(5):
            ts = base + timedelta(minutes=30 * i)
            snaps.append(_snap(ts, 90.0 - 15.0 * i, status="Charging"))
        conn = _seed_db(tmp_path, snaps)
        assert battery_drain_rate(conn, days=7)["value"] is None

    def test_glitches_filtered_by_plausibility(self, tmp_path: Path) -> None:
        base = _base(2)
        snaps = []
        # 1%/h real drain + a glitch pair (40% drop in 30 min = 80%/h)
        snaps.append(_snap(base, 90.0))
        snaps.append(_snap(base + timedelta(minutes=30), 89.5))
        snaps.append(_snap(base + timedelta(hours=1), 49.0))
        snaps.append(_snap(base + timedelta(hours=2), 48.5))
        conn = _seed_db(tmp_path, snaps)
        result = battery_drain_rate(conn, days=7)
        assert result["value"] is not None
        assert result["value"] <= 15.0  # glitch never dominates (median)


class TestStorageGrowth:
    def test_growth_and_eta(self, tmp_path: Path) -> None:
        base = _base(7)
        snaps = []
        for day in range(5):  # +1 GB/day on a 225 GB partition
            ts = base + timedelta(days=day)
            snaps.append(_snap(ts, 50.0, status="Full", used_gb=100.0 + day, total_gb=225.0))
        conn = _seed_db(tmp_path, snaps)
        result = storage_growth(conn, days=14)
        assert abs(result["value"] - 7.0) < 0.1  # GB/week
        # headroom to 90%: 0.9*225 - 104 = 98.5 GB at 7 GB/week -> ~98d
        assert 90 <= result["eta_days_to_90pct"] <= 105
        assert result["verdict"] == "ACT"  # >2 GB/week

    def test_insufficient_history_is_no_data(self, tmp_path: Path) -> None:
        base = _base(2)
        snaps = [_snap(base, 50.0, status="Full")]
        conn = _seed_db(tmp_path, snaps)
        result = storage_growth(conn, days=14)
        assert result["value"] is None
        assert result["verdict"] == "NO DATA"

    def test_finds_data_not_storage0(self, tmp_path: Path) -> None:
        """storage[0] is '/' on Samsung; /data must be found by name."""
        base = _base(6)
        snaps = []
        for day in range(4):
            snaps.append(
                _snap(base + timedelta(days=day), 50.0, status="Full", used_gb=100.0 + 2 * day)
            )
        conn = _seed_db(tmp_path, snaps)
        result = storage_growth(conn, days=14)
        assert result["value"] is not None  # slope from /data, not '/'

    def test_p95_pressure(self, tmp_path: Path) -> None:
        base = _base(6)
        snaps = []
        for i in range(100):
            ts = base + timedelta(hours=i)
            snaps.append(
                (
                    ts.isoformat(),
                    json_dumps(50.0, "Full", 100.0, 225.0).replace(
                        '"usage_percent": 50.0', '"usage_percent": 95.0'
                    ),
                )
            )
        conn = _seed_db(tmp_path, snaps)
        result = percentile_pressure(conn, "$.memory.usage_percent")
        assert result["value"] == 95.0
        assert result["verdict"] == "ACT"
