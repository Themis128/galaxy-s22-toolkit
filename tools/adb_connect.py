#!/usr/bin/env python3
"""Wireless ADB connection manager for the Galaxy S22+.

Wraps the library's config-driven resolution (diagnostics/config.yaml:
preferred USB serial wins, tailnet host auto-connect) with a user-facing
status/connect/reconnect CLI.

Usage:
    python tools/adb_connect.py status      # what is attached, what wins
    python tools/adb_connect.py connect     # connect + verify identity
    python tools/adb_connect.py reconnect   # drop Wi-Fi transport, redo it
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]


def load_wireless() -> dict | None:
    cfg = REPO / "diagnostics" / "config.yaml"
    if not cfg.exists():
        return None
    data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
    return (data.get("device") or {}).get("wireless_adb")


def make_client(serial: str | None = None):
    from phone import create_client

    c = create_client(serial=serial, wireless=load_wireless())
    if getattr(c, "serial", None) is None:
        raise SystemExit(
            "no serial resolved (multiple transports, no preference); "
            "set PHONE_ADB_SERIAL or device.wireless_adb.preferred_serial"
        )
    return c


def cmd_status() -> int:
    from phone.adb import AdbClient

    devices = AdbClient(serial=None).list_devices()
    if not devices:
        print("no devices attached")
        return 1
    for d in devices:
        kind = "USB" if ":" not in d["serial"] else "Wi-Fi"
        print(f"{d['serial']:<22} {d['state']:<8} {kind}")
    preferred = (load_wireless() or {}).get("preferred_serial")
    chosen = make_client().serial
    print(f"preferred_serial : {preferred or '(none)'}")
    print(f"resolved serial  : {chosen}")
    return 0


def cmd_connect() -> int:
    c = make_client()
    info = c.device.get_device_info()
    battery = c.battery.get_battery_info()
    print(f"connected : {c.serial}")
    print(f"device    : {info.model} (Android {info.android_version}, API {info.api_level})")
    print(f"battery   : {battery.level}% ({battery.status.value})")
    return 0


def cmd_reconnect() -> int:
    import subprocess

    wireless = load_wireless() or {}
    host = wireless.get("host")
    port = wireless.get("port", 5555)
    if not host:
        print("no wireless_adb.host in diagnostics/config.yaml", file=__import__("sys").stderr)
        return 1
    subprocess.run(["adb", "disconnect", f"{host}:{port}"], capture_output=True)
    print(f"dropped {host}:{port}")
    return cmd_connect()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "command", nargs="?", default="status", choices=["status", "connect", "reconnect"]
    )
    args = parser.parse_args()
    return {"status": cmd_status, "connect": cmd_connect, "reconnect": cmd_reconnect}[
        args.command
    ]()


if __name__ == "__main__":
    raise SystemExit(main())
