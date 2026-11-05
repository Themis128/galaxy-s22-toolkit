#!/usr/bin/env python3
"""SQLite persistence for historical device metrics."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Database location: dashboard/data/metrics.db
DB_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = DB_DIR / "metrics.db"

SCHEMA_VERSION = 1

SCHEMA_SQL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Raw metric snapshots (one row per collection cycle)
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc TEXT NOT NULL,           -- ISO8601 UTC timestamp
    device_json TEXT NOT NULL,      -- full device snapshot as JSON
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON snapshots(ts_utc);

-- Pre-aggregated hourly rollups for fast trend queries
CREATE TABLE IF NOT EXISTS hourly_rollups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hour_start_utc TEXT NOT NULL,   -- YYYY-MM-DD HH:00:00
    metric_path TEXT NOT NULL,      -- e.g. "battery.level", "thermal.zones[0].temp_c"
    metric_type TEXT NOT NULL,      -- "scalar", "array_min", "array_max", "array_avg"
    value REAL NOT NULL,
    sample_count INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(hour_start_utc, metric_path, metric_type)
);
CREATE INDEX IF NOT EXISTS idx_hourly_hour ON hourly_rollups(hour_start_utc);
CREATE INDEX IF NOT EXISTS idx_hourly_metric ON hourly_rollups(metric_path);

-- Daily rollups (computed from hourly)
CREATE TABLE IF NOT EXISTS daily_rollups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day_start_utc TEXT NOT NULL,    -- YYYY-MM-DD 00:00:00
    metric_path TEXT NOT NULL,
    metric_type TEXT NOT NULL,
    value REAL NOT NULL,
    sample_count INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(day_start_utc, metric_path, metric_type)
);
CREATE INDEX IF NOT EXISTS idx_daily_day ON daily_rollups(day_start_utc);
CREATE INDEX IF NOT EXISTS idx_daily_metric ON daily_rollups(metric_path);
"""


class MetricsDB:
    """Thread-safe SQLite wrapper for metric persistence."""

    def __init__(self, db_path: Path = DB_PATH, max_snapshots: int = 172800) -> None:
        self.db_path = db_path
        self.max_snapshots = max_snapshots  # ~10 days at 5s interval
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get thread-local connection."""
        if not hasattr(self._local, "conn"):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn: sqlite3.Connection = sqlite3.connect(
                self.db_path,
                timeout=30.0,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            # Pragmas for performance and durability
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA cache_size=-8192")  # 8MB cache
            self._local.conn = conn
        return self._local.conn  # type: ignore[return-value]

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for explicit transactions."""
        conn = self._get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _init_db(self) -> None:
        """Create tables and run migrations."""
        with self.transaction() as conn:
            conn.executescript(SCHEMA_SQL)
            # Record schema version
            cur = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
            row = cur.fetchone()
            if row is None:
                conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
            elif row["version"] < SCHEMA_VERSION:
                # Future migrations would go here
                conn.execute(
                    "UPDATE schema_version SET version = ? WHERE version = ?",
                    (SCHEMA_VERSION, row["version"]),
                )

    def insert_snapshot(self, snapshot: dict[str, Any]) -> int:
        """Store a raw snapshot. Returns the row ID."""
        ts = snapshot.get("timestamp")
        if ts is None:
            ts = datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z"
        with self.transaction() as conn:
            cur = conn.execute(
                "INSERT INTO snapshots (ts_utc, device_json) VALUES (?, ?)",
                (ts, json.dumps(snapshot, separators=(",", ":"))),
            )
            self._maybe_prune(conn)
            return cur.lastrowid

    def _maybe_prune(self, conn: sqlite3.Connection) -> None:
        """Keep only the most recent max_snapshots rows."""
        if self.max_snapshots <= 0:
            return
        cur = conn.execute("SELECT COUNT(*) AS c FROM snapshots")
        count = cur.fetchone()["c"]
        if count > self.max_snapshots:
            to_delete = count - self.max_snapshots
            conn.execute(
                "DELETE FROM snapshots WHERE id IN "
                "(SELECT id FROM snapshots ORDER BY ts_utc ASC LIMIT ?)",
                (to_delete,),
            )

    def get_snapshots(
        self,
        hours: int = 24,
        limit: int = 10000,
        metric_path: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve snapshots within the time window."""
        cutoff = (
            datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours)
        ).isoformat() + "Z"
        with self.transaction() as conn:
            if metric_path:
                # Extract a specific metric from the JSON blob
                sql = """
                    SELECT ts_utc, json_extract(device_json, ?) AS value
                    FROM snapshots
                    WHERE ts_utc >= ? AND json_type(json_extract(device_json, ?)) IS NOT NULL
                    ORDER BY ts_utc DESC
                    LIMIT ?
                """
                cur = conn.execute(sql, (f"$.{metric_path}", cutoff, f"$.{metric_path}", limit))
                return [{"timestamp": r["ts_utc"], metric_path: r["value"]} for r in cur.fetchall()]
            else:
                cur = conn.execute(
                    "SELECT device_json FROM snapshots WHERE ts_utc >= ? ORDER BY ts_utc DESC LIMIT ?",
                    (cutoff, limit),
                )
                return [json.loads(r["device_json"]) for r in cur.fetchall()]

    def get_latest_snapshot(self) -> dict[str, Any] | None:
        """Get the most recent snapshot."""
        with self.transaction() as conn:
            cur = conn.execute("SELECT device_json FROM snapshots ORDER BY ts_utc DESC LIMIT 1")
            row = cur.fetchone()
            return json.loads(row["device_json"]) if row else None

    # --- Aggregation helpers ---

    def _flatten_metrics(self, obj: dict[str, Any], prefix: str = "") -> dict[str, float]:
        """Extract all scalar numeric values from a nested dict, dot-notation keys."""
        out: dict[str, float] = {}
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (int, float)):
                out[path] = float(v)
            elif isinstance(v, dict):
                out.update(self._flatten_metrics(v, path))
            elif isinstance(v, list):
                # Handle arrays of objects (e.g., thermal.zones)
                for i, item in enumerate(v):
                    if isinstance(item, dict):
                        out.update(self._flatten_metrics(item, f"{path}[{i}]"))
                    elif isinstance(item, (int, float)):
                        out[f"{path}[{i}]"] = float(item)
        return out

    def compute_hourly_rollups(self, hours_back: int = 2) -> int:
        """Aggregate raw snapshots into hourly rollups for the recent window."""
        cutoff = (
            datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours_back)
        ).isoformat() + "Z"
        with self.transaction() as conn:
            # Pull raw snapshots in the window
            cur = conn.execute(
                "SELECT ts_utc, device_json FROM snapshots WHERE ts_utc >= ? ORDER BY ts_utc",
                (cutoff,),
            )
            rows = cur.fetchall()
            if not rows:
                return 0

            # Group by hour
            from collections import defaultdict

            hourly: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for r in rows:
                ts = r["ts_utc"]
                # Normalize to space format: YYYY-MM-DD HH:00:00
                # Input can be: 2026-11-04T00:00:00.000000Z or 2026-11-04T00:00:00.000000
                # Extract date and hour: first 13 chars = YYYY-MM-DDTHH
                date_hour = ts[:13]  # e.g., "2026-11-04T00"
                hour_start = date_hour.replace("T", " ") + ":00:00"  # "2026-11-04 00:00:00"
                data = json.loads(r["device_json"])
                hourly[hour_start].append(data)

            inserted = 0
            for hour_start, snapshots in hourly.items():
                # Collect all scalar values across snapshots in this hour
                metric_values: dict[str, list[float]] = defaultdict(list)
                for snap in snapshots:
                    flat = self._flatten_metrics(snap)
                    for path, val in flat.items():
                        metric_values[path].append(val)

                # Upsert rollups
                for path, values in metric_values.items():
                    if not values:
                        continue
                    avg_val = sum(values) / len(values)
                    min_val = min(values)
                    max_val = max(values)
                    for metric_type, value in [
                        ("avg", avg_val),
                        ("min", min_val),
                        ("max", max_val),
                    ]:
                        conn.execute(
                            """
                            INSERT INTO hourly_rollups (hour_start_utc, metric_path, metric_type, value, sample_count)
                            VALUES (?, ?, ?, ?, ?)
                            ON CONFLICT(hour_start_utc, metric_path, metric_type) DO UPDATE SET
                                value = excluded.value,
                                sample_count = excluded.sample_count,
                                created_at = datetime('now')
                            """,
                            (hour_start, path, metric_type, value, len(values)),
                        )
                        inserted += 1
            return inserted

    def compute_daily_rollups(self, days_back: int = 2) -> int:
        """Aggregate hourly rollups into daily rollups."""
        cutoff_day = (
            datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_back)
        ).strftime("%Y-%m-%d")
        with self.transaction() as conn:
            cur = conn.execute(
                """
                SELECT date(hour_start_utc) AS day_start_utc, metric_path, metric_type,
                       AVG(value) AS avg_val, SUM(sample_count) AS total_count
                FROM hourly_rollups
                WHERE hour_start_utc >= ?
                GROUP BY date(hour_start_utc), metric_path, metric_type
                """,
                (cutoff_day + " 00:00:00",),
            )
            rows = cur.fetchall()
            inserted = 0
            for r in rows:
                conn.execute(
                    """
                    INSERT INTO daily_rollups (day_start_utc, metric_path, metric_type, value, sample_count)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(day_start_utc, metric_path, metric_type) DO UPDATE SET
                        value = excluded.value,
                        sample_count = excluded.sample_count,
                        created_at = datetime('now')
                    """,
                    (
                        r["day_start_utc"] + " 00:00:00",
                        r["metric_path"],
                        r["metric_type"],
                        r["avg_val"],
                        r["total_count"],
                    ),
                )
                inserted += 1
            return inserted

    # --- Query APIs for dashboard ---

    def get_hourly_trend(self, metric_path: str, hours: int = 24) -> list[dict[str, Any]]:
        """Hourly averaged values for a metric."""
        cutoff = (
            datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours)
        ).strftime("%Y-%m-%d %H:00:00")
        with self.transaction() as conn:
            cur = conn.execute(
                """
                SELECT hour_start_utc AS timestamp, value
                FROM hourly_rollups
                WHERE metric_path = ? AND metric_type = 'avg' AND hour_start_utc >= ?
                ORDER BY hour_start_utc
                """,
                (metric_path, cutoff),
            )
            return [{"timestamp": r["timestamp"], "value": r["value"]} for r in cur.fetchall()]

    def get_daily_trend(self, metric_path: str, days: int = 30) -> list[dict[str, Any]]:
        """Daily averaged values for a metric."""
        cutoff = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)).strftime(
            "%Y-%m-%d"
        )
        with self.transaction() as conn:
            cur = conn.execute(
                """
                SELECT day_start_utc AS timestamp, value
                FROM daily_rollups
                WHERE metric_path = ? AND metric_type = 'avg' AND day_start_utc >= ?
                ORDER BY day_start_utc
                """,
                (metric_path, cutoff),
            )
            return [{"timestamp": r["timestamp"], "value": r["value"]} for r in cur.fetchall()]

    def get_metric_stats(self, metric_path: str, hours: int = 24) -> dict[str, Any]:
        """Min/max/avg/count for a metric over the window."""
        cutoff = (
            datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours)
        ).isoformat() + "Z"
        with self.transaction() as conn:
            cur = conn.execute(
                """
                SELECT
                    MIN(json_extract(device_json, ?)) AS min_val,
                    MAX(json_extract(device_json, ?)) AS max_val,
                    AVG(json_extract(device_json, ?)) AS avg_val,
                    COUNT(*) AS count
                FROM snapshots
                WHERE ts_utc >= ? AND json_type(json_extract(device_json, ?)) IN ('integer', 'real')
                """,
                (
                    f"$.{metric_path}",
                    f"$.{metric_path}",
                    f"$.{metric_path}",
                    cutoff,
                    f"$.{metric_path}",
                ),
            )
            row = cur.fetchone()
            return dict(row) if row else {}

    def list_available_metrics(self, hours: int = 24) -> list[str]:
        """Discover metric paths that have data in the window (sampled)."""
        cutoff = (
            datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours)
        ).isoformat() + "Z"
        with self.transaction() as conn:
            # Sample a few recent snapshots and extract keys
            cur = conn.execute(
                "SELECT device_json FROM snapshots WHERE ts_utc >= ? ORDER BY ts_utc DESC LIMIT 10",
                (cutoff,),
            )
            paths: set[str] = set()
            for r in cur.fetchall():
                data = json.loads(r["device_json"])
                paths.update(self._flatten_metrics(data).keys())
            return sorted(paths)

    def close(self) -> None:
        """Close the thread-local connection."""
        if hasattr(self._local, "conn"):
            self._local.conn.close()
            del self._local.conn


# Global instance (initialized in dashboard/app.py)
metrics_db: MetricsDB | None = None


def init_metrics_db(db_path: Path | None = None, max_snapshots: int = 172800) -> MetricsDB:
    """Initialize the global metrics database."""
    global metrics_db
    metrics_db = MetricsDB(db_path or DB_PATH, max_snapshots)
    return metrics_db


def get_metrics_db() -> MetricsDB:
    """Get the global metrics database instance."""
    if metrics_db is None:
        return init_metrics_db()
    return metrics_db
