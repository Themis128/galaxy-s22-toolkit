"""Tests for dashboard.metrics_db: persistence, trends, stats, pruning."""

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from dashboard.metrics_db import MetricsDB


def _snap(ts: datetime, level: float, temp: float = 30.0) -> dict[str, Any]:
    """A minimal nested snapshot like the collector produces."""
    return {
        "timestamp": ts.isoformat(),
        "battery": {"level": level, "temperature": temp},
        "memory": {"available_mb": 4000.0 + level},
    }


class TestSnapshotRoundtrip:
    def test_insert_and_get_latest(self, tmp_db: MetricsDB) -> None:
        ts = datetime.now(timezone.utc).replace(tzinfo=None)
        tmp_db.insert_snapshot(_snap(ts, 88.0))
        latest = tmp_db.get_latest_snapshot()
        assert latest is not None
        assert latest["battery"]["level"] == 88.0
        assert latest["memory"]["available_mb"] == 4088.0

    def test_latest_returns_none_when_empty(self, tmp_db: MetricsDB) -> None:
        assert tmp_db.get_latest_snapshot() is None

    def test_timestamp_generated_when_missing(self, tmp_db: MetricsDB) -> None:
        tmp_db.insert_snapshot({"battery": {"level": 50.0}})
        assert tmp_db.get_latest_snapshot() is not None


class TestTrends:
    def test_hourly_trend_after_rollup(self, tmp_db: MetricsDB) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for minutes_ago in range(0, 90, 5):  # 18 snapshots over 90 min
            ts = now - timedelta(minutes=minutes_ago)
            tmp_db.insert_snapshot(_snap(ts, 80.0 + minutes_ago % 5))
        inserted = tmp_db.compute_hourly_rollups(hours_back=2)
        assert inserted > 0
        trend = tmp_db.get_hourly_trend("battery.level", hours=24)
        assert 0 < len(trend) <= 24
        values = [row["value"] for row in trend if row["value"] is not None]
        assert values and all(79.0 <= v <= 85.0 for v in values)

    def test_daily_trend_after_rollup(self, tmp_db: MetricsDB) -> None:
        """Daily rollups aggregate from hourly rollups, so chain both."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for days_ago in range(3):
            ts = now - timedelta(days=days_ago)
            tmp_db.insert_snapshot(_snap(ts, 70.0 + days_ago))
        assert tmp_db.compute_hourly_rollups(hours_back=24 * 4) > 0
        assert tmp_db.compute_daily_rollups(days_back=3) > 0
        trend = tmp_db.get_daily_trend("battery.level", days=30)
        assert trend and all(row["value"] is not None for row in trend)
        # unknown metric -> empty, not error
        assert tmp_db.get_daily_trend("metric_never_stored", days=30) == []

    def test_stats(self, tmp_db: MetricsDB) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        levels = [60.0, 60.5, 61.0, 61.5]
        for i, level in enumerate(levels):
            tmp_db.insert_snapshot(_snap(now - timedelta(minutes=i), level))
        stats = tmp_db.get_metric_stats("battery.level", hours=24)
        assert stats["count"] == 4
        assert stats["min_val"] == 60.0
        assert stats["max_val"] == 61.5
        assert stats["avg_val"] == pytest.approx(60.75)

    def test_stats_empty_metric(self, tmp_db: MetricsDB) -> None:
        stats = tmp_db.get_metric_stats("no.such.metric", hours=24)
        assert stats.get("count", 0) == 0

    def test_list_available_metrics(self, tmp_db: MetricsDB) -> None:
        tmp_db.insert_snapshot(_snap(datetime.now(timezone.utc).replace(tzinfo=None), 55.0))
        metrics = tmp_db.list_available_metrics(hours=24)
        assert "battery.level" in metrics
        assert "memory.available_mb" in metrics


class TestRetention:
    def test_pruning_keeps_max_snapshots(self, tmp_db: MetricsDB) -> None:
        db = MetricsDB(db_path=tmp_db.db_path, max_snapshots=5)
        for i in range(8):
            ts = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=i)
            db.insert_snapshot(_snap(ts, 50.0))
        latest = db.get_latest_snapshot()
        assert latest is not None
        # 8 inserted, only the 5 most recent survive
        stats = db.get_metric_stats("battery.level", hours=24)
        assert stats["count"] == 5
        db.close()
