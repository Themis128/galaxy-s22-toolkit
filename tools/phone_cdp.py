#!/usr/bin/env python3
"""phone_cdp - drive the phone's Chrome via CDP over adb forward.

Chrome on Android exposes DevTools on localabstract:chrome_devtools_remote.
Forward it to localhost:9333 and you get full DOM control — far more reliable
than uiautomator taps for web flows (SPAs, autocomplete, canvases).

Requires: `uv run --with websockets python tools/phone_cdp.py ...`
(or pip install websockets)

Usage:
    phone_cdp.py targets                      # list page targets
    phone_cdp.py eval '<js>' [substr]         # Runtime.evaluate on matching page
    phone_cdp.py open <url>                   # launch URL in Chrome, print target id
    phone_cdp.py shot <substr> <file.png>`    # Page.captureScreenshot -> PNG
"""

from __future__ import annotations

import asyncio
import base64
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

PORT = 19333
JS_WS = f"ws://localhost:{PORT}"


def _adb() -> str:
    # WSL-native adb first: `adb forward` binds on the host running the adb
    # server, so a Windows adb.exe listener is unreachable from WSL localhost.
    import shutil

    for c in (str(Path.home() / ".local/bin/adb"), "adb"):
        if shutil.which(c) or Path(c).exists():
            return c
    return "/mnt/c/Users/tbaltzakis/AppData/Local/Android/Sdk/platform-tools/adb.exe"


def _serial() -> str:
    """Pick a serial this adb server actually sees (USB serial may be absent
    under WSL-native adb; tailnet/LAN transports are)."""
    adb = _adb()
    out = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=15).stdout
    serials = [ln.split()[0] for ln in out.splitlines()[1:] if ln.strip().endswith("device")]
    if not serials:
        raise SystemExit("no adb devices; connect phone first")
    # prefer tailnet host, then LAN, then anything
    for pref in ("100.", "192.168."):
        for s in serials:
            if s.startswith(pref):
                return s
    return serials[0]


def ensure_forward() -> None:
    adb, serial = _adb(), _serial()
    subprocess.run(
        [adb, "-s", serial, "forward", f"tcp:{PORT}", "localabstract:chrome_devtools_remote"],
        capture_output=True,
        timeout=15,
    )


def _get(path: str) -> dict:
    with urllib.request.urlopen(f"http://localhost:{PORT}{path}", timeout=10) as r:
        return json.load(r)


def find_target(substr: str = "") -> dict:
    targets = _get("/json")
    pages = [t for t in targets if t.get("type") == "page"]
    if substr:
        pages = [t for t in pages if substr in t.get("url", "")]
    if not pages:
        raise SystemExit(f"no page target matching {substr!r}; run `targets` to list")
    return pages[0]


async def _eval(
    ws_url: str, expr: str, method: str = "Runtime.evaluate", params: dict | None = None
) -> dict:
    import websockets

    async with websockets.connect(ws_url, max_size=50 * 1024 * 1024) as ws:
        await ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": method,
                    "params": params
                    or {"expression": expr, "returnByValue": True, "awaitPromise": True},
                }
            )
        )
        while True:
            m = json.loads(await ws.recv())
            if m.get("id") == 1:
                return m.get("result", {})


def cmd_targets() -> int:
    ensure_forward()
    for t in _get("/json"):
        if t.get("type") == "page":
            print(f"{t['id']:>5}  {t['url'][:95]}")
    return 0


def cmd_eval(expr: str, substr: str) -> int:
    ensure_forward()
    t = find_target(substr)
    res = asyncio.run(_eval(t["webSocketDebuggerUrl"], expr))
    val = res.get("result", {}).get("value")
    print(val if val is not None else res.get("result", {}).get("description"))
    return 0


def cmd_open(url: str) -> int:
    adb, serial = _adb(), _serial()
    subprocess.run(
        [
            adb,
            "-s",
            serial,
            "shell",
            "am",
            "start",
            "-a",
            "android.intent.action.VIEW",
            "-p",
            "com.android.chrome",
            "-d",
            url,
        ],
        capture_output=True,
        timeout=15,
    )
    ensure_forward()
    import time

    for _ in range(30):
        time.sleep(1)
        try:
            t = find_target("")
            if url.split("/")[2] in t["url"]:
                print(t["id"], t["url"][:95])
                return 0
        except SystemExit:
            continue
    print("target not found", file=sys.stderr)
    return 1


def cmd_shot(substr: str, out: str) -> int:
    ensure_forward()
    t = find_target(substr)
    res = asyncio.run(
        _eval(
            t["webSocketDebuggerUrl"], "", method="Page.captureScreenshot", params={"format": "png"}
        )
    )
    data = res.get("data")
    if not data:
        print("capture failed", file=sys.stderr)
        return 1
    Path(out).write_bytes(base64.b64decode(data))
    print(out)
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    if cmd == "targets":
        return cmd_targets()
    if cmd == "eval":
        return cmd_eval(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
    if cmd == "open":
        return cmd_open(sys.argv[2])
    if cmd == "shot":
        return cmd_shot(
            sys.argv[2] if len(sys.argv) > 2 else "",
            sys.argv[3] if len(sys.argv) > 3 else "/tmp/phone_cdp.png",
        )
    print(f"unknown command {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
