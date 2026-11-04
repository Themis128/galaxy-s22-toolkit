#!/usr/bin/env python3
"""Security-patch age check for the connected Galaxy S22+.

Reports model, Android version, security patch date, days-old, and a
verdict; --open-settings launches the system update screen on the phone.

Usage:
    python tools/update_check.py                  # report
    python tools/update_check.py --open-settings  # open update screen
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]


def load_client():
    """Connect like production: diagnostics/config.yaml wireless settings."""
    from phone import create_client

    wireless = None
    cfg = REPO / "diagnostics" / "config.yaml"
    if cfg.exists():
        data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
        wireless = (data.get("device") or {}).get("wireless_adb")
    c = create_client(wireless=wireless)
    if getattr(c, "serial", None) is None:
        raise SystemExit("multiple transports attached; set PHONE_ADB_SERIAL")
    return c


def verdict_for_age(days: int) -> str:
    """Binary verdict thresholds: <60 OK, 60-90 AGING, >90 OUTDATED."""
    if days < 60:
        return "OK"
    if days <= 90:
        return "AGING"
    return "OUTDATED"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--open-settings", action="store_true", help="open the update screen")
    args = parser.parse_args()
    c = load_client()
    info = c.device.get_device_info()
    patch = info.security_patch
    try:
        patch_date = datetime.strptime(patch[:10], "%Y-%m-%d").date()
    except ValueError:
        print("cannot parse patch date:", patch)
        return 1
    days = (date.today() - patch_date).days
    verdict = verdict_for_age(days)
    print("model          :", info.model)
    print("android        :", info.android_version, "(API", str(info.api_level) + ")")
    print("security patch :", patch, f"({days} days old)")
    print("verdict        :", verdict)
    if days > 90:
        print("action         : Settings -> Software update -> Download and install")
    if args.open_settings:
        c.execute("shell", "am", "start", "-a", "android.settings.SYSTEM_UPDATE_SETTINGS")
        print("opened system update screen on device")
    return 0 if verdict != "OUTDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
