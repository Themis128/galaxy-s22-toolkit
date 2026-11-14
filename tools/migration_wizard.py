#!/usr/bin/env python3
"""Migration wizard — move user content between two Galaxy phones over ADB.

The open-source equivalent of Wondershare's migration wizard: old-phone ->
staging -> new-phone content moves, honest about what ADB cannot move
(contacts, WhatsApp history, authenticator seeds).

    plan      — read-only checklist: what is on the old phone, what ADB
                can move, what needs on-device steps
    export    — pull user-content roots from the attached phone into
                data/migration/<ts>/
    import    — push staged content onto the attached phone (never
                overwrites unless --overwrite AND --yes)
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

try:
    from phone import create_client
except ImportError:  # pragma: no cover
    create_client = None  # type: ignore[assignment]

STAGING = REPO / "data" / "migration"
MIGRATE_ROOTS = (
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


def _human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def staging_dir(ts: str) -> Path:
    """data/migration/<ts> staging root for one migration pass."""
    return STAGING / ts


def _device_serials(client: object) -> list[str]:
    """Attached device serials (authorized only) from the adb server."""
    devices = client.list_devices()  # type: ignore[attr-defined]
    return [str(d["serial"]) for d in devices if d.get("state") == "device"]


def _resolve_serial(client: object, serial: str | None) -> str | None:
    """Two-device rule: refuse when ambiguous; single device auto-selects.

    Returns None when the transport itself is unusable (no adb server /
    no device), which callers turn into an honest error message.
    """
    serials = _device_serials(client)
    if serial:
        return serial
    if len(serials) == 1:
        return serials[0]
    if len(serials) > 1:
        raise SystemExit(
            "Multiple devices attached — pass --serial <S> to choose the "
            f"migration target. Attached: {', '.join(serials)}"
        )
    return None


def _remote_walk(client: object, root: str) -> list[tuple[str, int]]:
    """(remote_path, size) for every file under `root`; [] when absent.

    Uses `find <root> -type f -printf`-free toybox-compatible approach:
    `ls -lR` is slow on big trees; instead walk with `find` and read the
    size column from its output. Falls back to [] on any error.
    """
    try:
        out = client.execute("shell", "find", root, "-type", "f")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - absent root is normal
        return []
    files: list[tuple[str, int]] = []
    for line in str(out).splitlines():
        path = line.strip()
        if not path:
            continue
        files.append((path, 0))
    return files


ADB_MOVABLE_NOTE = (
    "ADB moves shared storage only: photos/videos/downloads/documents/"
    "recordings/ringtones/music + WhatsApp media files (history itself "
    "needs the official QR flow)."
)
CANNOT_MOVE = (
    "What ADB cannot move (do these on-device):",
    "  - Contacts: Google account sync or Smart Switch",
    "  - Messages/call logs: Google backup or Smart Switch",
    "  - WhatsApp chats: official QR transfer (see phone-whatsapp guide)",
    "  - Authenticator seeds: export them FIRST (they never migrate)",
    "  - App data: per-app restore flows only (adb backup is dead)",
)


def _cmd_plan(client: object) -> int:
    for root in MIGRATE_ROOTS:
        files = _remote_walk(client, root)
        print(f"{root:<40} {len(files):>6} files")
    print()
    print(ADB_MOVABLE_NOTE)
    print()
    for line in CANNOT_MOVE:
        print(line)
    return 0


def _cmd_export(client: object, ts: str, yes: bool, serial: str | None) -> int:
    staging = staging_dir(ts)
    plan: list[tuple[str, str]] = []
    for root in MIGRATE_ROOTS:
        for remote_path, _size in _remote_walk(client, root):
            rel = remote_path.removeprefix("/sdcard/")
            plan.append((remote_path, rel))
    if not plan:
        print("Nothing to export (no user-content roots present).")
        return 0
    print(f"Export plan: {len(plan)} file(s) -> {staging}")
    for _remote_path, rel in plan[:20]:
        print(f"  pull {rel}")
    if len(plan) > 20:
        print(f"  ... and {len(plan) - 20} more")
    if not yes:
        print("Dry run (pass --yes to execute).")
        return 0
    print("Pulling...")
    pulled = 0
    for remote_path, rel in plan:
        local = staging / rel
        local.parent.mkdir(parents=True, exist_ok=True)
        try:
            client.pull(remote_path, str(local))  # type: ignore[attr-defined]
            pulled += 1
        except Exception as exc:  # noqa: BLE001 - per-file honesty
            print(f"  FAILED pull {rel}: {exc}")
    print(f"Exported {pulled}/{len(plan)} file(s) -> {staging}")
    return 0 if pulled == len(plan) else 1


def _cmd_import(client: object, ts: str, yes: bool, overwrite: bool) -> int:
    staging = staging_dir(ts)
    if not staging.is_dir():
        print(f"No staged migration at {staging} - run export first.")
        return 1
    plan: list[Path] = sorted(staging.rglob("*"))
    plan = [p for p in plan if p.is_file()]
    if not plan:
        print(f"Nothing staged under {staging}.")
        return 0
    print(f"Import plan: {len(plan)} file(s) from {staging}")
    for p in plan[:20]:
        print(f"  push {p.relative_to(staging).as_posix()}")
    if len(plan) > 20:
        print(f"  ... and {len(plan) - 20} more")
    if not yes:
        print("Dry run (pass --yes to execute).")
        return 0
    pushed, skipped = 0, 0
    for p in plan:
        rel = p.relative_to(staging).as_posix()
        remote = f"/sdcard/{rel}"
        if not overwrite:
            out = client.execute("shell", f'test -e "{remote}" && echo Y || echo N')  # type: ignore[attr-defined]
            if str(out).strip().endswith("Y"):
                skipped += 1
                continue
        try:
            client.push(str(p), remote)  # type: ignore[attr-defined]
            pushed += 1
        except Exception as exc:  # noqa: BLE001 - per-file honesty
            print(f"  FAILED push {rel}: {exc}")
    print(
        f"Imported {pushed}/{len(plan)} file(s); skipped {skipped} existing"
        " (import never overwrites unless --overwrite AND --yes)"
    )
    return 0


def _client(serial: str | None) -> object:
    if create_client is None:
        raise SystemExit("phone-lib not importable")
    import yaml

    with open(REPO / "diagnostics" / "config.yaml", encoding="utf-8") as fh:
        device_cfg = (yaml.safe_load(fh) or {}).get("device", {})
    wireless = device_cfg.get("wireless_adb") or None
    if wireless:
        wireless = {**wireless, "preferred_serial": device_cfg.get("serial")}
    return create_client(serial, wireless=wireless)


def _latest_staging() -> str | None:
    """Newest staging timestamp under data/migration, or None."""
    if not STAGING.is_dir():
        return None
    candidates = sorted(p.name for p in STAGING.iterdir() if p.is_dir())
    return candidates[-1] if candidates else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "export", "import"):
        sub.add_parser(name)
        sub.choices[name].add_argument("--serial")
        sub.choices[name].add_argument("--yes", action="store_true")
        sub.choices[name].add_argument("--overwrite", action="store_true")
    sub.choices["import"].add_argument("--ts", help="staging timestamp to import")
    args = ap.parse_args(argv)

    probe = _client(args.serial)
    resolved = _resolve_serial(probe, args.serial)
    if resolved is None:
        print("No attached device found.")
        return 1

    if args.cmd == "plan":
        return _cmd_plan(probe)
    if args.cmd == "export":
        export_ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        return _cmd_export(probe, export_ts, args.yes, resolved)
    staged_ts = args.ts or _latest_staging()
    if not staged_ts:
        print("No staged migration found - run export first.")
        return 1
    return _cmd_import(probe, staged_ts, args.yes, args.overwrite)
