#!/usr/bin/env python3
"""Incremental phone backup — the Wondershare "My Backup" equivalent, local-only.

Backs up the phone's user content to data/phone-mirror/ over ADB (USB or
wireless) with an incremental engine: a JSON manifest (remote path -> size +
mtime) drives per-file pulls, so only new/changed files transfer. Runs
headless from a scheduled task and writes a status file the dashboard reads.

Usage:
    python tools/backup_phone.py incremental [--serial S]   # default
    python tools/backup_phone.py full [--serial S]          # ignore manifest deltas
    python tools/backup_phone.py status
"""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, cast

REPO = Path(__file__).resolve().parents[1]
MIRROR = REPO / "data" / "phone-mirror"
MANIFEST = MIRROR / ".backup-manifest.json"
STATUS = REPO / "data" / "backup-status.json"
if __name__ == "__main__":
    sys.path.insert(0, str(REPO))

try:
    from phone import create_client
except ImportError:  # pragma: no cover
    create_client = None  # type: ignore[assignment]

# User-content roots backed up (device paths)
BACKUP_ROOTS = (
    "/sdcard/DCIM",
    "/sdcard/Pictures",
    "/sdcard/Movies",
    "/sdcard/Download",
    "/sdcard/Documents",
    "/sdcard/Recordings",
    "/sdcard/Ringtones",
    "/sdcard/Music",
    "/sdcard/Android/media/com.whatsapp",
    "/sdcard/Android/media/com.whatsapp.w4b",
)
# Junk directories never backed up
SKIP_PATTERNS = (".trashed", "/.thumbnails", "/cache", "intl_rel")


def _client(serial: str | None) -> Any:
    import yaml

    with open(REPO / "diagnostics" / "config.yaml", encoding="utf-8") as f:
        device_cfg = (yaml.safe_load(f) or {}).get("device", {})
    wireless = device_cfg.get("wireless_adb") or None
    if wireless:
        wireless = {**wireless, "preferred_serial": device_cfg.get("serial")}
    return create_client(serial, wireless=wireless)


def _walk_remote(c: Any, root: str) -> list[dict[str, Any]]:
    """Recursive ls -laR walk of a device directory (typed entries)."""
    entries: list[dict[str, Any]] = []
    stack = [root]
    seen: set[str] = set()
    while stack:
        current = stack.pop()
        if current in seen or any(p in current for p in SKIP_PATTERNS):
            continue
        seen.add(current)
        try:
            out = c.execute("shell", "ls", "-la", current)
        except Exception:  # noqa: BLE001 - unreadable dirs are skipped
            continue
        for line in out.splitlines():
            m = re.match(
                r"^([\-dl][rwxsStT\-]{9})\s+\S+\s+\S+\s+\S+\s+(\d+)\s+"
                r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\s+(.+)$",
                line.rstrip(),
            )
            if not m:
                continue
            perms, size, name = m.group(1), int(m.group(2)), m.group(3)
            if name in (".", ".."):
                continue
            child = posixpath.join(current, name)
            if perms.startswith("d"):
                stack.append(child)
            else:
                rel = posixpath.relpath(child, "/sdcard/")
                entries.append(
                    {
                        "remote": child,
                        "rel": rel,
                        "size": size,
                        "mtime": f"{line.split()[-3]} {line.split()[-2]}",
                    }
                )
    return entries


def load_manifest() -> dict[str, dict[str, Any]]:
    try:
        return cast(dict[str, dict[str, Any]], json.loads(MANIFEST.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return {}


def save_manifest(manifest: dict[str, dict[str, Any]]) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=1), encoding="utf-8")


def needs_pull(entry: dict[str, Any], manifest: dict[str, dict[str, Any]], full: bool) -> bool:
    """Incremental decision for one remote entry (pure; unit-tested).

    False only when NOT full, the manifest knows the file, size and mtime
    both match, and the local copy exists."""
    prev = manifest.get(entry["rel"])
    if full or prev is None:
        return True
    if prev.get("size") != entry["size"] or prev.get("mtime") != entry["mtime"]:
        return True
    return not (MIRROR / entry["rel"]).exists()


def run_backup(serial: str | None, full: bool = False) -> dict[str, Any]:
    if create_client is None:
        return {"status": "error", "error": "phone-lib not importable"}
    started = datetime.now()
    c = _client(serial)
    manifest = load_manifest()
    copied = changed = skipped = errors = 0
    bytes_copied = 0

    for root in BACKUP_ROOTS:
        entries = _walk_remote(c, root)
        for e in entries:
            rel = e["rel"]
            remote = e["remote"]
            dest = MIRROR / rel
            prev = manifest.get(rel)
            if not needs_pull(e, manifest, full):
                skipped += 1
                continue
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                c.pull(remote, str(dest))
                manifest[rel] = {"size": e["size"], "mtime": e["mtime"]}
                copied += 1
                bytes_copied += e["size"]
                if prev is not None:
                    changed += 1
            except Exception as exc:  # noqa: BLE001 - one file never aborts
                errors += 1
                if errors <= 5:
                    print(f"  error: {rel}: {exc}")

    save_manifest(manifest)
    files_total = len(manifest)
    report = {
        "status": "ok",
        "mode": "full" if full else "incremental",
        "finished": datetime.now().isoformat(),
        "duration_s": round((datetime.now() - started).total_seconds(), 1),
        "copied": copied,
        "changed": changed,
        "skipped_unchanged": skipped,
        "errors": errors,
        "bytes_copied": bytes_copied,
        "files_total": files_total,
    }
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def status_report() -> dict[str, Any]:
    try:
        return cast(dict[str, Any], json.loads(STATUS.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return {"status": "never-run"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("incremental", "full"):
        p = sub.add_parser(name)
        p.add_argument("--serial")
    sub.add_parser("status")
    args = parser.parse_args(argv)

    if args.cmd == "status":
        print(json.dumps(status_report(), indent=2))
        return 0
    report = run_backup(args.serial, full=args.cmd == "full")
    print(
        f"{report['mode']}: copied {report['copied']} ({report.get('bytes_copied', 0) / 1e6:.1f} MB), "
        f"unchanged {report['skipped_unchanged']}, errors {report['errors']}, "
        f"total files {report['files_total']} in {report['duration_s']}s"
    )
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
