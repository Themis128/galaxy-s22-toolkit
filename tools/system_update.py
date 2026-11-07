#!/usr/bin/env python3
"""Drive the OTA system-update flow on the attached Galaxy phone.

The security-patch install itself must ultimately be confirmed on the
device, but every UI step up to and including the install tap can be
driven over ADB: wake the screen, open Settings > Software update, tap
"Download and install", and later tap "Install now" (which reboots).

Usage:
    python tools/system_update.py status                 # patch-age report
    python tools/system_update.py open                   # open update screen
    python tools/system_update.py ui                     # dump readable UI tree
    python tools/system_update.py tap --text "Download and install"
    python tools/system_update.py download               # dry-run: find the button
    python tools/system_update.py download --confirm     # actually tap it
    python tools/system_update.py install --confirm-reboot   # tap Install now
"""

from __future__ import annotations

# ruff: noqa: T201  # CLI output requires print statements
import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "phone-lib" / "src"))
sys.path.insert(0, str(REPO))

from phone import AdbClient  # noqa: E402
from tools.update_check import load_client, verdict_for_age  # noqa: E402

# ===== UI dump parsing (pure; unit-testable) =====


def parse_bounds(bounds: str) -> tuple[int, int]:
    """Center of a uiautomator bounds attr like '[x1,y1][x2,y2]'."""
    parts = bounds.replace("][", ",").strip("[]").split(",")
    x1, y1, x2, y2 = (int(p) for p in parts)
    return (x1 + x2) // 2, (y1 + y2) // 2


def _safe_fromstring(xml: str) -> ET.Element[str]:
    """Parse a uiautomator dump, refusing entity-bearing XML.

    UI dumps are plain <hierarchy> documents; a DOCTYPE or entity
    declaration would only appear in hostile input (billion-laughs /
    entity expansion), so refuse it instead of parsing."""
    head = xml[:4096].upper()
    if "<!DOCTYPE" in head or "<!ENTITY" in head:
        raise ET.ParseError("entity-bearing XML refused")
    return ET.fromstring(xml)


def find_tappable(xml: str, needle: str) -> tuple[int, int] | None:
    """Find a node whose text or content-desc contains ``needle``
    (case-insensitive) and return its tap center, preferring clickable
    nodes. None when not found."""
    try:
        root = _safe_fromstring(xml)
    except ET.ParseError:
        return None
    fallback: tuple[int, int] | None = None
    for node in root.iter("node"):
        label = (node.get("text", "") + " " + node.get("content-desc", "")).lower()
        if needle.lower() not in label:
            continue
        try:
            center = parse_bounds(node.get("bounds", "[0,0][0,0]"))
        except (ValueError, IndexError):
            continue
        if node.get("clickable") == "true":
            return center
        if fallback is None:
            fallback = center
    return fallback


def summarize_ui(xml: str, limit: int = 40) -> list[str]:
    """Readable one-line summary of the interesting text nodes."""
    try:
        root = _safe_fromstring(xml)
    except ET.ParseError:
        return ["<unparseable UI dump>"]
    lines = []
    for node in root.iter("node"):
        text = node.get("text", "").strip()
        desc = node.get("content-desc", "").strip()
        label = text or desc
        if not label:
            continue
        clickable = " [tap]" if node.get("clickable") == "true" else ""
        lines.append(f"{label}{clickable}")
        if len(lines) >= limit:
            break
    return lines


# ===== Device interaction =====


def dump_ui(client: AdbClient) -> str:
    """Dump the current window's UI hierarchy and return the XML."""
    client.execute("shell", "uiautomator", "dump", "/sdcard/toolkit_ui.xml", check=False)
    return client.execute("shell", "cat", "/sdcard/toolkit_ui.xml")


def wake_if_needed(client: AdbClient) -> bool:
    """Wake the screen; return False when a lockscreen still blocks input."""
    focus = client.execute("shell", "dumpsys", "window", check=False)
    if "Keyguard" in focus or "NotificationShade" in focus:
        client.execute("shell", "input", "keyevent", "KEYCODE_WAKEUP", check=False)
        focus = client.execute("shell", "dumpsys", "window", check=False)
    return "Keyguard" not in focus


def open_update_screen(client: AdbClient) -> None:
    client.execute(
        "shell",
        "am",
        "start",
        "-a",
        "android.settings.SYSTEM_UPDATE_SETTINGS",
    )


def battery_percent(client: AdbClient) -> int:
    out = client.execute("shell", "dumpsys", "battery")
    for line in out.splitlines():
        if line.strip().startswith("level:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                break
    return 0


def tap_label(client: AdbClient, needle: str) -> bool:
    """Tap the first tappable node containing ``needle``. False if absent."""
    center = find_tappable(dump_ui(client), needle)
    if center is None:
        return False
    x, y = center
    client.execute("shell", "input", "tap", str(x), str(y))
    return True


def cmd_status(client: AdbClient) -> int:
    """Security-patch report (mirrors update_check)."""
    info = client.device.get_device_info()
    try:
        from datetime import date, datetime

        patch_date = datetime.strptime(info.security_patch[:10], "%Y-%m-%d").date()
        days = (date.today() - patch_date).days
        verdict = verdict_for_age(days)
    except ValueError:
        print("cannot parse patch date:", info.security_patch)
        return 1
    print(f"model          : {info.model}")
    print(f"security patch : {info.security_patch} ({days} days old)")
    print(f"verdict        : {verdict}")
    return 0 if verdict != "OUTDATED" else 1


def cmd_open(client: AdbClient) -> int:
    if not wake_if_needed(client):
        print("Screen is locked - unlock the phone and retry.")
        return 1
    open_update_screen(client)
    print("System update screen opened on the device.")
    return 0


def cmd_ui(client: AdbClient) -> int:
    if not wake_if_needed(client):
        print("Screen is locked - unlock the phone and retry.")
        return 1
    for line in summarize_ui(dump_ui(client)):
        print(line)
    return 0


def cmd_tap(client: AdbClient, text: str, confirm: bool) -> int:
    if not wake_if_needed(client):
        print("Screen is locked - unlock the phone and retry.")
        return 1
    center = find_tappable(dump_ui(client), text)
    if center is None:
        print(f"No tappable element matching {text!r} on screen. Current UI:")
        for line in summarize_ui(dump_ui(client)):
            print(" ", line)
        return 1
    print(f"target: {text!r} at {center}")
    if not confirm:
        print("dry-run only - pass --confirm to tap")
        return 2
    client.execute("shell", "input", "tap", str(center[0]), str(center[1]))
    print("tapped.")
    return 0


def cmd_download(client: AdbClient, confirm: bool) -> int:
    """Navigate: open update screen and tap 'Download and install'."""
    if not wake_if_needed(client):
        print("Screen is locked - unlock the phone and retry.")
        return 1
    open_update_screen(client)
    label = "Download and install"
    center = find_tappable(dump_ui(client), label)
    if center is None:
        # Some One UI builds gate it behind "Check for updates" first
        if tap_label(client, "Check for updates"):
            import time

            time.sleep(5)
            center = find_tappable(dump_ui(client), label)
    if center is None:
        print(f"{label!r} not found (update may already be downloaded or up to date). UI:")
        for line in summarize_ui(dump_ui(client)):
            print(" ", line)
        return 1
    print(f"target: {label!r} at {center}")
    if not confirm:
        print("dry-run only - pass --confirm to start the OTA download")
        return 2
    client.execute("shell", "input", "tap", str(center[0]), str(center[1]))
    print("Download requested on the device. The download proceeds in the")
    print("background; re-run with 'install --confirm-reboot' once it completes.")
    return 0


def cmd_install(client: AdbClient, confirm_reboot: bool) -> int:
    """Tap 'Install now' once the OTA is fully downloaded. Reboots the phone."""
    level = battery_percent(client)
    if level < 30:
        print(f"Battery at {level}% - Samsung requires ~30%+ to install. Charge first.")
        return 1
    if not wake_if_needed(client):
        print("Screen is locked - unlock the phone and retry.")
        return 1
    center = find_tappable(dump_ui(client), "Install now") or find_tappable(
        dump_ui(client), "Restart now"
    )
    if center is None:
        print("No pending install prompt found. UI:")
        for line in summarize_ui(dump_ui(client)):
            print(" ", line)
        return 1
    print(f"target: install prompt at {center} - THE PHONE WILL REBOOT")
    if not confirm_reboot:
        print("dry-run only - pass --confirm-reboot to install")
        return 2
    client.execute("shell", "input", "tap", str(center[0]), str(center[1]))
    print("Install tapped. The phone reboots into the update; wireless ADB")
    print("auto-reconnects after it comes back (create_client auto_connect).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="patch-age report")
    sub.add_parser("open", help="open Settings > Software update")
    sub.add_parser("ui", help="dump the current screen as a readable list")
    p_tap = sub.add_parser("tap", help="tap the first element matching --text")
    p_tap.add_argument("--text", required=True)
    p_tap.add_argument("--confirm", action="store_true")
    p_dl = sub.add_parser("download", help="open update screen + tap 'Download and install'")
    p_dl.add_argument("--confirm", action="store_true")
    p_in = sub.add_parser("install", help="tap 'Install now' (reboots the phone)")
    p_in.add_argument("--confirm-reboot", action="store_true")
    args = parser.parse_args(argv)

    client: Any = load_client()
    if args.cmd == "status":
        return cmd_status(client)
    if args.cmd == "open":
        return cmd_open(client)
    if args.cmd == "ui":
        return cmd_ui(client)
    if args.cmd == "tap":
        return cmd_tap(client, args.text, args.confirm)
    if args.cmd == "download":
        return cmd_download(client, args.confirm)
    if args.cmd == "install":
        return cmd_install(client, args.confirm_reboot)
    return 1


if __name__ == "__main__":
    sys.exit(main())
