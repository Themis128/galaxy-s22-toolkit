#!/usr/bin/env python3
"""Screen Mirror & Control via scrcpy — the open-source Wondershare Screen Mirror.

Launches scrcpy (Genymobile, open source) against the resolved device serial —
USB or wireless, no root required. Records to data/mirrors/ with --record.

Usage:
    python tools/mirror.py start [--serial S] [--max-size 1280]
    python tools/mirror.py record [--serial S]   # records to data/mirrors/
    python tools/mirror.py stop                  # kills running scrcpy
    python tools/mirror.py status
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MIRRORS_DIR = REPO / "data" / "mirrors"

if __name__ == "__main__":
    sys.path.insert(0, str(REPO))

try:
    from phone import create_client
except ImportError:  # pragma: no cover - running outside the repo
    create_client = None  # type: ignore[assignment]


def find_scrcpy() -> str | None:
    """Locate the scrcpy binary (PATH or winget shim)."""
    return shutil.which("scrcpy")


def resolve_serial(explicit: str | None = None) -> str | None:
    """Resolve the device serial using the toolkit's standard resolution."""
    if explicit:
        return explicit
    if create_client is None:
        return None
    try:
        import yaml

        cfg_root = REPO / "diagnostics" / "config.yaml"
        device_cfg = {}
        with open(cfg_root, encoding="utf-8") as f:
            device_cfg = (yaml.safe_load(f) or {}).get("device", {})
        wireless = device_cfg.get("wireless_adb") or None
        if wireless:
            wireless = {**wireless, "preferred_serial": device_cfg.get("serial")}
        client = create_client(None, wireless=wireless)
        return getattr(client, "serial", None)
    except Exception:  # noqa: BLE001 - serial resolution is best-effort
        return None


def build_scrcpy_args(
    serial: str,
    record: Path | None = None,
    max_size: int = 1280,
    time_limit: int | None = None,
) -> list[str]:
    """scrcpy command line for the serial (pure; unit-tested).

    scrcpy 5.x removed --no-audio-on-failure; audio defaults are fine.
    Recordings use --time-limit so scrcpy exits cleanly and finalizes the
    MP4 (taskkill mid-recording leaves an unfinalized 48-byte stub)."""
    args = ["scrcpy", "-s", serial, "--max-size", str(max_size)]
    if record is not None:
        args += ["--record", str(record), "--no-playback"]
        if time_limit:
            args += ["--time-limit", str(time_limit)]
    return args


def start(serial: str | None, record: bool, max_size: int, time_limit: int | None = None) -> int:
    scrcpy = find_scrcpy()
    if not scrcpy:
        print("scrcpy not installed — winget install Genymobile.scrcpy")
        return 1
    resolved = resolve_serial(serial)
    if not resolved:
        print("No device serial resolved (is the phone connected?)")
        return 1
    rec_path = None
    if record:
        MIRRORS_DIR.mkdir(parents=True, exist_ok=True)
        rec_path = MIRRORS_DIR / f"mirror-{datetime.now():%Y%m%d-%H%M%S}.mp4"
    args = [scrcpy, *build_scrcpy_args(resolved, rec_path, max_size, time_limit)[1:]]
    print("launching:", " ".join(args))
    try:
        subprocess.Popen(
            args, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
    except OSError as exc:
        print(f"launch failed: {exc}")
        return 1
    if rec_path is not None:
        print(f"recording to {rec_path}" + (f" for {time_limit}s" if time_limit else ""))
    return 0


def stop() -> int:
    if sys.platform != "win32":
        print("stop is Windows-only (taskkill)")
        return 1
    proc = subprocess.run(["taskkill", "/IM", "scrcpy.exe", "/F"], capture_output=True, text=True)
    ok = proc.returncode == 0
    print(
        "scrcpy stopped"
        if ok
        else f"no running scrcpy ({proc.stdout.strip() or proc.stderr.strip()})"
    )
    return 0 if ok else 1


def status() -> int:
    scrcpy = find_scrcpy()
    resolved = resolve_serial(None)
    print(f"scrcpy   : {scrcpy or 'NOT INSTALLED'}")
    print(f"serial   : {resolved or 'none resolved'}")
    if MIRRORS_DIR.is_dir():
        recordings = sorted(MIRRORS_DIR.glob("mirror-*.mp4"))
        print(f"recordings: {len(recordings)} in {MIRRORS_DIR}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_start = sub.add_parser("start", help="launch scrcpy for the attached device")
    p_start.add_argument("--serial")
    p_start.add_argument("--max-size", type=int, default=1280)
    p_rec = sub.add_parser("record", help="launch scrcpy recording to data/mirrors/")
    p_rec.add_argument("--serial")
    p_rec.add_argument("--max-size", type=int, default=1280)
    p_rec.add_argument(
        "--time-limit", type=int, default=30, help="seconds to record (clean finalize)"
    )
    sub.add_parser("stop", help="kill running scrcpy")
    sub.add_parser("status", help="show scrcpy/serial/recordings status")
    args = parser.parse_args(argv)
    if args.cmd == "start":
        return start(args.serial, False, args.max_size)
    if args.cmd == "record":
        return start(args.serial, True, args.max_size, args.time_limit)
    if args.cmd == "stop":
        return stop()
    return status()


if __name__ == "__main__":
    raise SystemExit(main())
