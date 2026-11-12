#!/usr/bin/env python3
"""Wireless ADB watchdog — keeps the container's phone path alive.

The dashboard container reaches the phone over wireless ADB only
(Docker Desktop cannot pass USB into containers). Classic `adb tcpip 5555`
does not survive an adbd restart (USB replug, USB config change, phone
reboot), and when it drops the container collector logs "Device not
connected" every 5 s until someone re-enables it from the USB host.

This watchdog runs from a scheduled task every 5 minutes and:

1. finds the phone over USB (`adb devices`, no colon in serial);
2. if adbd is not in TCP mode (`service.adb.tcp.port` != 5555):
   `adb tcpip 5555`, waits for the listener;
3. ensures the host's wireless transports (LAN + configured tailnet host)
   are connected, so both the host CLI and the container heal;
4. appends everything to logs/adb-watchdog.log (capped at 1 MB).

The container's collector self-heals once the phone listens again (it
resets its cached client on error), so no container restart is needed.

Register (Git Bash — MSYS_NO_PATHCONV=1 stops /every-5-minutes becoming a
path; run elevated once):
    MSYS_NO_PATHCONV=1 schtasks /create /tn "Wireless ADB Watchdog" \
      /tr "pythonw.exe C:\\dev\\galaxy-s22-toolkit\\tools\\adb_watchdog.py" \
      /sc minute /mo 5 /f

Exit codes: 0 = phone listening on 5555 (healthy or healed);
1 = phone seen over USB but still not listening after the heal attempt;
2 = no phone over USB at all (nothing this watchdog can do).
"""

from __future__ import annotations

import argparse
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
LOG = REPO / "logs" / "adb-watchdog.log"
LOG_CAP = 1_000_000
CONFIG = REPO / "diagnostics" / "config.yaml"


def log(line: str) -> None:
    """Append a stamped line to the log, capping the file at LOG_CAP."""
    try:
        if LOG.exists() and LOG.stat().st_size > LOG_CAP:
            LOG.write_text(
                LOG.read_text(encoding="utf-8", errors="replace")[-LOG_CAP // 2 :],
                encoding="utf-8",
            )
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"[{stamp}] {line}\n")
    except OSError:
        pass


def run(cmd: list[str], timeout: float = 20) -> tuple[int, str]:
    """Run a command; returns (returncode, combined output). Never raises."""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,  # noqa: S603
        )
        return proc.returncode, (proc.stdout + proc.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)


def load_config() -> dict[str, Any]:
    """device section of config.yaml; {} when unreadable (stdlib fallbacks)."""
    try:
        import yaml  # noqa: PLC0415 - optional at runtime; defaults cover absence

        with open(CONFIG, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        device = data.get("device") or {}
        return device if isinstance(device, dict) else {}
    except Exception:  # noqa: BLE001 - watchdog must never raise
        return {}


def usb_phone_serial(preferred: str) -> str | None:
    """USB-attached phone serial (no colon = USB transport)."""
    rc, out = run(["adb", "devices"])
    if rc != 0:
        return None
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device" and ":" not in parts[0]:
            return parts[0]
    return None


def adbd_tcp_port(serial: str) -> str | None:
    """Current value of service.adb.tcp.port (None when adbd is in USB mode)."""
    rc, out = run(["adb", "-s", serial, "shell", "getprop", "service.adb.tcp.port"])
    val = out.strip() if rc == 0 else ""
    return val or None


def wait_for_listener(serial: str, host: str, port: str, tries: int = 6) -> bool:
    """Poll until adbd accepts connections on host:port (adbd restarts on tcpip)."""
    for _ in range(tries):
        time.sleep(2)
        rc, out = run(["adb", "-s", serial, "shell", "getprop", "service.adb.tcp.port"])
        if rc == 0 and out.strip() == port:
            return True
    return False


def ensure_wireless_transport(host: str, port: str) -> bool:
    """`adb connect host:port` unless already connected; True when connected."""
    _, out = run(["adb", "devices"])
    if f"{host}:{port}" in out and "offline" not in out.split(f"{host}:{port}")[1][:20]:
        return True
    rc, out = run(["adb", "connect", f"{host}:{port}"])
    return rc == 0 and "connected" in out.lower()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (default; for the task)")
    ap.add_argument(
        "--lan-host",
        default="192.168.1.77",
        help="phone's LAN IP (the container's PHONE_ADB_HOST path)",
    )
    ap.add_argument("--port", default="5555")
    ap.add_argument("--quiet", action="store_true", help="log only on action/failure")
    args = ap.parse_args(argv)

    cfg = load_config()
    preferred = str(cfg.get("serial") or "")
    wireless = cfg.get("wireless_adb") or {}
    tailnet_host = str(wireless.get("host") or "") if isinstance(wireless, dict) else ""

    serial = usb_phone_serial(preferred)
    if serial is None:
        log("no USB-attached phone - nothing to do")
        return 2

    port = adbd_tcp_port(serial)
    if port == args.port:
        if not args.quiet:
            log(f"healthy: {serial} already listening on :{args.port}")
    else:
        log(f"{serial}: adbd in USB mode (tcp.port={port!r}) - enabling tcpip {args.port}")
        rc, out = run(["adb", "-s", serial, "tcpip", args.port])
        log(f"  adb tcpip -> rc={rc} {out.splitlines()[0] if out else ''}")
        if not wait_for_listener(serial, args.lan_host, args.port):
            log(f"FAIL: {serial} not listening on :{args.port} after heal attempt")
            return 1
        log(f"  {serial} listening on :{args.port}")

    # Host transports: LAN first (container path), then the configured
    # tailnet host (host CLI path). Failures here are non-fatal - the
    # phone listening is what the container needs.
    if not ensure_wireless_transport(args.lan_host, args.port):
        log(f"warn: could not connect {args.lan_host}:{args.port} from this host")
    if tailnet_host:
        ensure_wireless_transport(tailnet_host, args.port)
    log(f"ok: wireless ADB ensured (usb={serial}, lan={args.lan_host}:{args.port})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
