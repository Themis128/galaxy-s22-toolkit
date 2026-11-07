#!/usr/bin/env python3
"""WhatsApp chat migration guide — drives WhatsApp's OFFICIAL transfer flow.

Third parties cannot merge into WhatsApp's end-to-end-encrypted store, so the
legitimate path is WhatsApp's own "Transfer chats" (QR, Android<->iPhone, no
root) — this tool automates the OLD phone side (opens the transfer screen)
and prints exactly what to do on the new one. Backup-based flows (Google
Drive / local crypt15 + wa-crypt-tools decryption for READ export) are
covered by phone-recover.

Usage:
    python tools/whatsapp_transfer.py check   # WhatsApp installed? version?
    python tools/whatsapp_transfer.py guide   # open the transfer screen + steps
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

try:
    from phone import create_client
except ImportError:  # pragma: no cover
    create_client = None  # type: ignore[assignment]


def _client(serial: str | None) -> Any:
    import yaml

    with open(REPO / "diagnostics" / "config.yaml", encoding="utf-8") as f:
        device_cfg = (yaml.safe_load(f) or {}).get("device", {})
    wireless = device_cfg.get("wireless_adb") or None
    if wireless:
        wireless = {**wireless, "preferred_serial": device_cfg.get("serial")}
    return create_client(serial, wireless=wireless)


def _ui_helpers() -> tuple[Any, Any]:
    """Load find_tappable/summarize_ui from tools/system_update.py."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_system_update", REPO / "tools" / "system_update.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.find_tappable, mod.summarize_ui


def check(serial: str | None) -> int:
    if create_client is None:
        print("phone-lib not importable")
        return 1
    c = _client(serial)
    packages = c.execute("shell", "pm", "list", "packages")
    for app in ("com.whatsapp", "com.whatsapp.w4b"):
        installed = f"package:{app}" in packages
        version = "?"
        if installed:
            dump = c.execute("shell", "dumpsys", "package", app)
            m = next((ln for ln in dump.splitlines() if "versionName" in ln), "")
            version = m.split("versionName=")[-1].strip() if m else "?"
        print(f"{app}: {'installed ' + version if installed else 'NOT installed'}")
    print("\nOfficial transfer options:")
    print("  - QR chat transfer (Settings > Chats > Transfer chats) - Android<->iPhone, no root")
    print("  - Google Drive backup > restore on the new phone")
    print("  - Local crypt15 + wa-crypt-tools decryption for READ export (phone-recover)")
    return 0


def guide(serial: str | None) -> int:
    """Open WhatsApp > Settings > Chats on the old phone and dump the state."""
    if create_client is None:
        print("phone-lib not importable")
        return 1
    c = _client(serial)
    find_tappable, summarize_ui = _ui_helpers()

    # WhatsApp's chat-transfer screen is deep-linked; the Settings > Chats
    # route is the stable path across versions.
    c.execute(
        "shell",
        "am",
        "start",
        "-n",
        "com.whatsapp/.HomeActivity",
    )
    subprocess.run(["sleep", "2"], check=False)
    for _ in range(2):
        dump = c.execute("shell", "uiautomator", "dump", "/dev/tty")
        center = find_tappable(dump, "chats") or find_tappable(dump, "settings")
        if center:
            c.execute("shell", "input", "tap", str(center[0]), str(center[1]))
            subprocess.run(["sleep", "1"], check=False)
    dump = c.execute("shell", "uiautomator", "dump", "/dev/tty")
    print("Current screen (transfer screen target):")
    for line in summarize_ui(dump):
        print("  ", line)
    print(
        "\nOn the OLD phone: Settings > Chats > Transfer chats > Start (generates a QR).\n"
        "On the NEW phone: install WhatsApp + verify the SAME number, then scan the QR.\n"
        "The transfer runs phone-to-phone over a local hotspot - no cloud, no root."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("check", "guide"):
        p = sub.add_parser(name)
        p.add_argument("--serial")
    args = parser.parse_args(argv)
    return check(args.serial) if args.cmd == "check" else guide(args.serial)


if __name__ == "__main__":
    raise SystemExit(main())
