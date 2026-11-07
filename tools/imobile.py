#!/usr/bin/env python3
"""iOS device support — the libimobiledevice CLI (Phone Manager/Backup for iPhone/iPad).

Usage:
    python tools/imobile.py info                     # identity + iOS version
    python tools/imobile.py backup [--full] [--dir D]
    python tools/imobile.py restore --dir D [--yes]
    python tools/imobile.py screenshot               # data/artifacts/ios-<ts>.png
    python tools/imobile.py apps                     # installed app list
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ARTIFACTS = REPO / "data" / "artifacts"
if __name__ == "__main__":
    sys.path.insert(0, str(REPO))

try:
    from phone.imobile import IMobileClient
except ImportError:  # pragma: no cover
    IMobileClient = None  # type: ignore[assignment,misc]


def _client(udid: str | None) -> IMobileClient:
    assert IMobileClient is not None
    return IMobileClient(udid)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("info", "backup", "restore", "screenshot", "apps"):
        p = sub.add_parser(name)
        p.add_argument("--udid")
    sub.choices["backup"].add_argument("--full", action="store_true")
    sub.choices["backup"].add_argument("--dir", default=str(REPO / "data" / "ios-backups"))
    sub.choices["restore"].add_argument("--dir", required=True)
    sub.choices["restore"].add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)

    if IMobileClient is None:
        print("phone-lib not importable")
        return 1
    try:
        client = _client(args.udid)
    except Exception as exc:  # noqa: BLE001 - honest degradation
        print(f"iOS device unavailable: {exc}")
        return 1

    if args.cmd == "info":
        info = client.get_info()
        print(f"name : {info.name}")
        print(f"model: {info.model}")
        print(f"iOS  : {info.ios_version}")
        print(f"udid : {info.udid}")
        return 0
    if args.cmd == "backup":
        print(
            f"Backing up {args.udid or 'device'} to {args.dir} (full={args.full}) — this can take hours"
        )
        out = client.backup(Path(args.dir), full=args.full)
        print("backup:", out.strip()[-200:])
        return 0
    if args.cmd == "restore":
        if not args.yes:
            print("restore wipes and replaces the device content — re-run with --yes")
            return 2
        print(f"Restoring from {args.dir} — keep the device unlocked")
        out = client.restore(Path(args.dir))
        print("restore:", out.strip()[-200:])
        return 0
    if args.cmd == "screenshot":
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        png = ARTIFACTS / f"ios-{datetime.now():%Y%m%d-%H%M%S}.png"
        client.screenshot(png)
        print("screenshot:", png)
        return 0
    apps = client.list_apps()
    print(f"{len(apps)} apps")
    for a in apps[:30]:
        print(" ", a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
