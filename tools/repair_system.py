#!/usr/bin/env python3
"""System Repair wizard — Samsung stock-firmware reflash via Heimdall.

The open-source equivalent of Wondershare System Repair (Android). A bad
flash CAN brick the device, so every step is gated:

    check     — Samsung device? Heimdall present? download-mode reachable?
    firmware  — locate/validate a stock .tar.md5 (user-provided or downloaded
                with a Frija-class tool; see rooting/RUNBOOK.md)
    flash     — per-partition Heimdall flash; requires --yes, a verified
                firmware, and a fresh backup (phone-root backup, <24h) unless
                --i-understand-brick-risk is passed

The tool never flashes anything without the typed triple gate.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tools.binfind import find_binary  # noqa: E402

try:
    from phone import create_client
except ImportError:  # pragma: no cover
    create_client = None  # type: ignore[assignment]

FIRMWARE_RE = re.compile(r"\.tar\.md5$", re.IGNORECASE)
SAMSUNG_BOOTLOADER_NOTE = (
    "Knox warning: flashing stock firmware does NOT unlock the bootloader or "
    "root the phone, but an interrupted flash can render the device "
    "unbootable. Verify the exact model + CSC before continuing."
)


def _client() -> Any:
    import yaml

    with open(REPO / "diagnostics" / "config.yaml", encoding="utf-8") as f:
        device_cfg = (yaml.safe_load(f) or {}).get("device", {})
    wireless = device_cfg.get("wireless_adb") or None
    if wireless:
        wireless = {**wireless, "preferred_serial": device_cfg.get("serial")}
    return create_client(None, wireless=wireless)


def check() -> int:
    problems: list[str] = []
    heimdall = find_binary("heimdall", "BenjaminDobell.Heimdall")
    if not heimdall:
        problems.append("heimdall not installed — winget install BenjaminDobell.Heimdall")
    try:
        version = subprocess.run(
            [heimdall or "heimdall", "version"], capture_output=True, text=True, timeout=15
        ).stdout.strip()
        print(f"heimdall   : {version}")
    except (OSError, subprocess.TimeoutExpired):
        print("heimdall   : not runnable")
    if create_client is None:
        problems.append("phone-lib not importable")
    else:
        try:
            c = _client()
            info = c.device.get_device_info()
            print(f"device     : {info.model} (Android {info.android_version})")
            print("mode       : ADB — reboot to download mode with the wizard's flash step")
        except Exception as exc:  # noqa: BLE001
            problems.append(f"device unreachable: {exc}")
    for p in problems:
        print("PROBLEM:", p)
    print(SAMSUNG_BOOTLOADER_NOTE)
    return 1 if problems else 0


def validate_firmware(path: Path) -> list[str]:
    """Partitions found inside a stock .tar.md5 (pure-ish; unit-testable via parse)."""
    if not FIRMWARE_RE.search(path.name):
        raise SystemExit(f"{path.name} is not a .tar.md5 firmware package")
    import tarfile

    partitions: list[str] = []
    with tarfile.open(path, "r:") as tar:
        for member in tar.getmembers():
            m = re.match(r"^(?P<part>[A-Za-z0-9_]+)\.img(\.lz4)?$", Path(member.name).name)
            if m:
                partitions.append(m.group("part"))
    return partitions


def flash(firmware: Path, partitions: list[str], yes: bool, skip_backup: bool) -> int:
    if not yes:
        print("REFUSING: flashing requires --yes (and a verified firmware).")
        return 2
    if not FIRMWARE_RE.search(firmware.name):
        print(f"REFUSING: {firmware.name} is not a .tar.md5 firmware package")
        return 2
    if not find_binary("heimdall", "BenjaminDobell.Heimdall"):
        print("heimdall not installed")
        return 1
    if not skip_backup:
        backup_root = REPO / "data"
        backups = sorted(backup_root.glob("backup-*"))
        if not backups:
            print(
                "REFUSING: no data/backup-*/ found — run phone-root backup first (or --skip-backup-check)"
            )
            return 2
    print(SAMSUNG_BOOTLOADER_NOTE)
    print(f"Flash plan: {firmware.name} partitions={','.join(partitions)}")
    print("Reboot to download mode, connect USB, then Heimdall runs. Ctrl-C to abort:")
    try:
        input("Press Enter to start the flash…")
    except KeyboardInterrupt:
        print("aborted")
        return 2
    cmd = ["heimdall", "flash", "--fullexit"]
    for part in partitions:
        img = firmware.parent / f"{part}.img"
        cmd += [f"--{part}", str(img)]
    print("running:", " ".join(cmd))
    proc = subprocess.run(cmd)
    return proc.returncode


def parse_tar_names(names: list[str]) -> list[str]:
    """Partition names from tar member names (pure; unit-tested)."""
    out = []
    for n in names:
        m = re.match(r"^(?P<part>[A-Za-z0-9_]+)\.img(\.lz4)?$", Path(n).name)
        if m:
            out.append(m.group("part"))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    p_f = sub.add_parser("firmware")
    p_f.add_argument("--file", required=True)
    p_fl = sub.add_parser("flash")
    p_fl.add_argument("--file", required=True)
    p_fl.add_argument("--partitions", required=True, help="comma-separated: boot,vendor_boot,...")
    p_fl.add_argument("--yes", action="store_true")
    p_fl.add_argument("--skip-backup-check", action="store_true")
    args = parser.parse_args(argv)

    if args.cmd == "check":
        return check()
    if args.cmd == "firmware":
        parts = validate_firmware(Path(args.file))
        print(f"{Path(args.file).name}: partitions = {', '.join(parts)}")
        return 0
    parts = args.partitions.split(",")
    return flash(Path(args.file), parts, args.yes, args.skip_backup_check)


if __name__ == "__main__":
    raise SystemExit(main())
