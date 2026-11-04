#!/usr/bin/env python3
"""Back up the dashboard metrics database out of its Docker volume.

The metrics history lives in the named volume `metrics-data`, so
`docker compose down --volumes` or `docker volume rm` wipes it. This
tool snapshots the database consistently (sqlite3 backup API, no app
downtime) inside the running dashboard container, copies it to
backups/metrics/ on the host, and prunes snapshots beyond --keep.

Usage:
    python tools/backup_metrics_db.py                # backup + prune
    python tools/backup_metrics_db.py --check        # report age only
    python tools/backup_metrics_db.py --keep 30      # keep more snapshots
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKUP_DIR = REPO / "backups" / "metrics"
CONTAINER_DB = "/app/dashboard/data/metrics.db"
SNAPSHOT_IN_CONTAINER = "/tmp/metrics-backup.db"


def prune_backups(directory: Path, keep: int) -> list[Path]:
    """Delete oldest snapshot files beyond `keep`; returns removed files."""
    files = sorted(directory.glob("metrics-*.db"))
    removed = []
    for old in files[:-keep] if keep > 0 else files:
        try:
            old.unlink()
            removed.append(old)
        except OSError as exc:
            print(f"  prune failed for {old.name}: {exc}", file=sys.stderr)
    return removed


def latest_backup(directory: Path) -> Path | None:
    files = sorted(directory.glob("metrics-*.db"))
    return files[-1] if files else None


def restore(db_file: Path) -> int:
    """Restore a backup into the metrics-data volume, safely.

    Order matters: stop the app FIRST, replace the file, then remove the
    stale WAL/SHM sidecars (a fresh DB's WAL reapplied over a restored
    file silently drops rows - verified in the first recovery drill),
    then start again.
    """
    if not db_file.exists():
        print(f"backup not found: {db_file}", file=sys.stderr)
        return 1

    def run(cmd: list[str]) -> bool:
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
        ok = r.returncode == 0
        if not ok:
            print(f"  failed: {' '.join(cmd)}: {r.stderr.strip()}", file=sys.stderr)
        return ok

    if not run(["docker", "compose", "stop", "dashboard"]):
        return 1
    if not run(
        [
            "docker",
            "compose",
            "cp",
            str(db_file),
            "dashboard:/app/dashboard/data/metrics.db",
        ]
    ):
        return 1
    # exec needs a running container; use a one-off on the volume instead
    if not run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            "galaxys222_metrics-data:/data",
            "python:3.12-slim",
            "sh",
            "-c",
            "rm -f /data/metrics.db-wal /data/metrics.db-shm",
        ]
    ):
        return 1
    if not run(["docker", "compose", "start", "dashboard"]):
        return 1
    print(f"restored {db_file.name} into the metrics-data volume")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--keep", type=int, default=14, help="snapshots to keep")
    parser.add_argument("--check", action="store_true", help="report age only")
    parser.add_argument(
        "--restore",
        metavar="FILE",
        help="restore a backup into the volume: stops the dashboard, "
        "replaces metrics.db, removes stale WAL sidecars (a fresh DB's "
        "WAL reapplied over a restored file drops rows - drill-verified), "
        "and restarts",
    )
    args = parser.parse_args(argv)

    if args.restore:
        return restore(Path(args.restore))

    latest = latest_backup(BACKUP_DIR)
    if args.check:
        if latest is None:
            print("no backups yet (run tools/backup_metrics_db.py)")
            return 1
        age = datetime.now() - datetime.fromtimestamp(latest.stat().st_mtime)
        ok = age < timedelta(hours=26)
        print(f"latest backup: {latest.name} ({age.total_seconds() / 3600:.1f}h old)")
        return 0 if ok else 1

    if (
        subprocess.run(["docker", "compose", "ps", "-q"], cwd=REPO, capture_output=True).returncode
        != 0
    ):
        print("docker not running or compose project down", file=sys.stderr)
        return 1

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = BACKUP_DIR / f"metrics-{stamp}.db"
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # Consistent snapshot via the sqlite3 backup API inside the container
    backup_code = (
        "import sqlite3;"
        f"src=sqlite3.connect('{CONTAINER_DB}');"
        f"dst=sqlite3.connect('{SNAPSHOT_IN_CONTAINER}');"
        "src.backup(dst);dst.close()"
    )
    r = subprocess.run(
        ["docker", "compose", "exec", "-T", "dashboard", "python", "-c", backup_code],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(f"in-container snapshot failed: {r.stderr.strip()}", file=sys.stderr)
        return 1

    r = subprocess.run(
        ["docker", "compose", "cp", f"dashboard:{SNAPSHOT_IN_CONTAINER}", str(dest)],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(f"copy out of container failed: {r.stderr.strip()}", file=sys.stderr)
        return 1

    removed = prune_backups(BACKUP_DIR, args.keep)
    print(
        f"backup: {dest.name} ({dest.stat().st_size} bytes)"
        + (f", pruned {len(removed)}" if removed else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
