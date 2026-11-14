#!/usr/bin/env python3
"""Selective restore — push chosen files from the phone mirror back onto a phone.

The open-source equivalent of Wondershare's selective restore: instead of
"restore everything", pick exactly what goes back:

    list      — inventory of what the mirror can restore (per-root counts)
    restore   — push selected mirror files to /sdcard/<rel> (dry-run by default)

Honesty note: this restores shared-storage content only (photos, videos,
downloads...). App data and app-private files CANNOT be restored over ADB
(adb backup is dead); those need per-app restore flows or Smart Switch.
"""

from __future__ import annotations

import argparse
import fnmatch
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

try:
    from phone import create_client
except ImportError:  # pragma: no cover
    create_client = None  # type: ignore[assignment]

MIRROR = REPO / "data" / "phone-mirror"
REMOTE_BASE = "/sdcard"
DISPLAY_CAP = 20


@dataclass(slots=True)
class MirrorFile:
    """One restorable file: rel maps 1:1 to /sdcard/<rel> on the phone."""

    rel: str
    local: str
    size: int
    mtime: float


def _human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def iter_mirror_files(mirror_root: Path) -> list[MirrorFile]:
    """All restorable files under the mirror.

    rel is the posix-style path under the mirror root, which maps 1:1 to
    /sdcard/<rel> on the phone.
    """
    if not mirror_root.is_dir():
        return []
    out: list[MirrorFile] = []
    for path in sorted(mirror_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(mirror_root).as_posix()
        st = path.stat()
        out.append(MirrorFile(rel=rel, local=str(path), size=st.st_size, mtime=st.st_mtime))
    return out


def filter_files(
    files: list[MirrorFile],
    roots: list[str] | None = None,
    pattern: str | None = None,
    newer_than: datetime | None = None,
) -> list[MirrorFile]:
    """AND-combined selection over rel paths: roots prefix, glob, mtime cutoff."""
    out = files
    if roots:
        out = [f for f in out if f.rel.split("/", 1)[0] in roots]
    if pattern:
        out = [f for f in out if fnmatch.fnmatch(f.rel, pattern)]
    if newer_than is not None:
        out = [f for f in out if f.mtime >= newer_than.timestamp()]
    return out


def plan_restore(
    files: list[MirrorFile], remote_exists: set[str]
) -> tuple[list[MirrorFile], list[str]]:
    """Partition files into (to_push, skipped_existing) given remote paths that exist."""
    to_push = [f for f in files if f.rel not in remote_exists]
    skipped = [f.rel for f in files if f.rel in remote_exists]
    return to_push, skipped


def _remote_exists(client: object, remote: str) -> bool:
    """Existence probe over shell (Y/N stdout, so errors can't masquerade)."""
    out = client.execute("shell", f'test -e "{remote}" && echo Y || echo N')  # type: ignore[attr-defined]
    return str(out).strip().endswith("Y")


def _cmd_list(mirror_root: Path, pattern: str | None) -> int:
    files = filter_files(iter_mirror_files(mirror_root), pattern=pattern)
    if not files:
        print("nothing to restore (mirror empty or filter matched nothing)")
        return 0
    by_root: dict[str, dict[str, float]] = {}
    for f in files:
        root = f.rel.split("/", 1)[0]
        agg = by_root.setdefault(root, {"count": 0, "bytes": 0.0})
        agg["count"] += 1
        agg["bytes"] += float(f.size)
    print(f"Mirror: {mirror_root}")
    for root in sorted(by_root):
        agg = by_root[root]
        print(f"  {root:<22} {int(agg['count']):>6} files  {_human(agg['bytes'])}")
    total = sum(a["bytes"] for a in by_root.values())
    total_n = sum(int(a["count"]) for a in by_root.values())
    print(f"  {'TOTAL':<22} {total_n:>6} files  {_human(total)}")
    return 0


def _cmd_restore(
    client: object,
    mirror_root: Path,
    roots: list[str] | None,
    pattern: str | None,
    newer_than: datetime | None,
    overwrite: bool,
    yes: bool,
) -> int:
    files = filter_files(iter_mirror_files(mirror_root), roots, pattern, newer_than)
    if not files:
        print("nothing to restore")
        return 0
    total_bytes = sum(f.size for f in files)
    print(f"Planned: {len(files)} file(s), {_human(total_bytes)} -> /sdcard")
    for f in files[:DISPLAY_CAP]:
        print(f"  push {f.rel}")
    if len(files) > DISPLAY_CAP:
        print(f"  ... and {len(files) - DISPLAY_CAP} more")
    if not yes:
        print("Dry run (pass --yes to execute).")
        return 0
    pushed, skipped = [], []
    for f in files:
        remote = f"{REMOTE_BASE}/{f.rel}"
        if not overwrite and _remote_exists(client, remote):
            skipped.append(f.rel)
            continue
        client.push(str(f.local), remote)  # type: ignore[attr-defined]
        pushed.append(f.rel)
    print(
        f"Restored {len(pushed)} file(s) ({_human(total_bytes)}); skipped {len(skipped)} existing"
    )
    for rel in skipped[:DISPLAY_CAP]:
        print(f"  skipped (exists): {rel}")
    return 0


def _parse_date(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise SystemExit(2) from exc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_list = sub.add_parser("list", help="inventory of restorable mirror content")
    p_list.add_argument("--pattern")
    p_restore = sub.add_parser("restore", help="push selected mirror files to the phone")
    for p in (p_list, p_restore):
        p.add_argument("--mirror", default=str(MIRROR), help="mirror root override")
    p_restore.add_argument("--roots", help="comma list of root dirs (DCIM,Pictures,...)")
    p_restore.add_argument("--pattern")
    p_restore.add_argument("--newer-than", help="YYYY-MM-DD mtime cutoff")
    p_restore.add_argument("--overwrite", action="store_true")
    p_restore.add_argument("--yes", action="store_true")
    p_restore.add_argument("--serial")
    args = ap.parse_args(argv)

    mirror_root = Path(args.mirror)
    newer_than = _parse_date(args.newer_than) if getattr(args, "newer_than", None) else None

    if args.cmd == "list":
        return _cmd_list(mirror_root, args.pattern)

    # restore: dry-run works without a device; --yes needs the phone
    client: object = None
    if args.yes:
        if create_client is None:
            print("phone-lib not importable")
            return 1
        import yaml

        with open(REPO / "diagnostics" / "config.yaml", encoding="utf-8") as fh:
            device_cfg = (yaml.safe_load(fh) or {}).get("device", {})
        wireless = device_cfg.get("wireless_adb") or None
        if wireless:
            wireless = {**wireless, "preferred_serial": device_cfg.get("serial")}
        client = create_client(args.serial, wireless=wireless)

    return _cmd_restore(
        client,
        mirror_root,
        args.roots,
        args.pattern,
        newer_than,
        args.overwrite,
        args.yes,
    )


if __name__ == "__main__":
    raise SystemExit(main())
