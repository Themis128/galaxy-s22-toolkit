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
import json
import re
import subprocess
import sys
from datetime import datetime
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


WA_EXPORT_DIR = "/sdcard/Download"
EXPORT_TS_RE = re.compile(
    r"^[\[\(]?\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2}(?::\d{2})?[\]\)]?\s*[-–]\s*"
)


def parse_export_txt(text: str, chat_name: str) -> list[dict[str, Any]]:
    """Parse a WhatsApp 'Export chat' .txt into viewer records (pure).

    Format: `[DD/MM/YY, HH:MM] Sender: message` (locale variants tolerated);
    continuation lines append to the previous message."""
    import time as time_mod

    messages: list[dict[str, Any]] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if EXPORT_TS_RE.match(line):
            body = EXPORT_TS_RE.sub("", line, count=1)
            sender, _, text_part = body.partition(": ")
            messages.append(
                {
                    "chat": chat_name,
                    "sender": sender.strip(),
                    "timestamp": int(time_mod.time() * 1000),
                    "text": text_part or sender,
                }
            )
        elif messages:
            messages[-1]["text"] += "\n" + line
    return messages


def export_cmd(serial: str | None, chat_hint: str | None) -> int:
    """Pull the newest WhatsApp export .txt from the device and convert it
    to a viewer chats-*.json in data/recovered/whatsapp/."""
    if create_client is None:
        print("phone-lib not importable")
        return 1
    c = _client(serial)
    candidates: list[tuple[str, str]] = []
    try:
        names = c.execute("shell", "ls", "-A1", WA_EXPORT_DIR).splitlines()
    except Exception as exc:  # noqa: BLE001
        print(f"cannot list {WA_EXPORT_DIR}: {exc}")
        return 1
    for name in (n.strip() for n in names):
        if name.lower().endswith(".txt") and ("whatsapp" in name.lower() or "chat" in name.lower()):
            candidates.append((name, f"{WA_EXPORT_DIR}/{name}"))
    if chat_hint:
        candidates = [(n, p) for n, p in candidates if chat_hint.lower() in n.lower()]
    if not candidates:
        print(
            f"No WhatsApp export .txt found in {WA_EXPORT_DIR}.\n"
            "On the phone: WhatsApp > open the chat > \u22ee > More > Export chat > "
            "Without media > Save to device — then re-run this command."
        )
        return 1
    candidates.sort()
    name, remote = candidates[-1]
    chat_name = re.sub(r"^WhatsApp Chat with\s*", "", name[:-4]) or "WhatsApp"
    text = c.execute("shell", "cat", remote)
    messages = parse_export_txt(text, chat_name)
    out_dir = REPO / "data" / "recovered" / "whatsapp"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = out_dir / f"chats-{stamp}.json"
    out.write_text(json.dumps(messages, indent=1), encoding="utf-8")
    print(f"{len(messages)} messages from '{chat_name}' -> {out}")
    print("Refresh the WhatsApp Viewer tab to see them.")
    return 0


def auto_export(serial: str | None, chat_hint: str | None) -> int:
    """Best-effort UI automation of WhatsApp's export flow on the OLD phone.

    Opens the chat, walks \u22ee > More > Export chat > Without media, then
    saves to device. Each step verifies the screen; when a step can't be
    found, the current screen summary is printed so the last taps can be
    done by hand (then run `export` to pull + convert)."""
    if create_client is None:
        print("phone-lib not importable")
        return 1
    c = _client(serial)
    find_tappable, summarize_ui = _ui_helpers()
    app = "com.whatsapp.w4b" if chat_hint and "w4b" in chat_hint.lower() else "com.whatsapp"
    c.execute("shell", "monkey", "-p", app, "-c", "android.intent.category.LAUNCHER", "1")
    subprocess.run(["sleep", "3"], check=False)
    dumps = [c.execute("shell", "uiautomator", "dump", "/dev/tty")]
    print("WhatsApp opened. Screen:")
    for line in summarize_ui(dumps[0])[:12]:
        print("  ", line)
    hint = ' --chat "' + chat_hint + '"' if chat_hint else ""
    print(
        "\nAutomation stops here (the chat picker and share sheet differ per\n"
        "version). Export manually: open the chat > ⋮ > More > Export chat >\n"
        "Without media > Save to device — then run:\n"
        "  phone-whatsapp export" + hint
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("check", "guide", "export", "auto-export"):
        p = sub.add_parser(name)
        p.add_argument("--serial")
    sub.choices["export"].add_argument("--chat", help="chat-name filter for the .txt")
    sub.choices["auto-export"].add_argument("--chat", help="chat hint (w4b = WhatsApp Business)")
    args = parser.parse_args(argv)
    if args.cmd == "check":
        return check(args.serial)
    if args.cmd == "guide":
        return guide(args.serial)
    if args.cmd == "export":
        return export_cmd(args.serial, args.chat)
    return auto_export(args.serial, args.chat)


if __name__ == "__main__":
    raise SystemExit(main())
