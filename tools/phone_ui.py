#!/usr/bin/env python3
"""phone_ui - UI automation CLI for the Galaxy S22+ over ADB.

Wraps phone.UiModule: uiautomator dumps, node search, coordinate taps,
text input, and pre-flight blocker checks (flip cover, lockscreen).

Usage:
    python tools/phone_ui.py status                      # focus + blockers
    python tools/phone_ui.py dump [--out FILE]           # print/save node list
    python tools/phone_ui.py find TEXT [--desc D]        # list matching nodes
    python tools/phone_ui.py tap-text TEXT [--desc D]    # tap node center
    python tools/phone_ui.py tap X Y                     # raw coordinate tap
    python tools/phone_ui.py type TEXT [--clear]         # input text
    python tools/phone_ui.py key CODE                    # keyevent (e.g. 4=back)
    python tools/phone_ui.py wait TEXT [--timeout N]     # poll until node exists
    python tools/phone_ui.py shot [FILE]                 # screenshot + pull
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from phone import AdbClient, UiNode

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "phone-lib" / "src"))
sys.path.insert(0, str(REPO / "tools"))


def _client() -> AdbClient:
    from adb_connect import load_wireless  # type: ignore[import-not-found]

    from phone import create_client

    return create_client(wireless=load_wireless())


def _node_line(n: UiNode) -> str:
    b = f"[{n.bounds.left},{n.bounds.top}][{n.bounds.right},{n.bounds.bottom}]" if n.bounds else "-"
    flags = f"{'C' if n.clickable else '-'}{'E' if n.enabled else '-'}"
    return (
        f"{b} {flags} text={n.text[:60]!r} desc={n.desc[:40]!r} "
        f"id={n.resource_id.split('/')[-1][:50]!r} cls={n.class_name.split('.')[-1]}"
    )


def main() -> int:
    p = argparse.ArgumentParser(prog="phone_ui")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status")

    d = sub.add_parser("dump")
    d.add_argument("--out", default=None)
    d.add_argument("--text", default=None, help="only nodes containing this text")

    f = sub.add_parser("find")
    f.add_argument("text")
    f.add_argument("--desc", default=None)
    f.add_argument("--exact", action="store_true")

    t = sub.add_parser("tap-text")
    t.add_argument("text")
    t.add_argument("--desc", default=None)
    t.add_argument("--exact", action="store_true")
    t.add_argument("--timeout", type=float, default=0.0)

    tt = sub.add_parser("tap")
    tt.add_argument("x", type=int)
    tt.add_argument("y", type=int)

    ty = sub.add_parser("type")
    ty.add_argument("text")
    ty.add_argument("--clear", action="store_true")

    k = sub.add_parser("key")
    k.add_argument("code")

    w = sub.add_parser("wait")
    w.add_argument("text")
    w.add_argument("--desc", default=None)
    w.add_argument("--timeout", type=float, default=10.0)

    s = sub.add_parser("shot")
    s.add_argument("file", nargs="?", default="/tmp/phone.png")

    args = p.parse_args()
    client = _client()
    ui = client.ui

    if args.cmd == "status":
        st = ui.status()
        for k_, v in st.items():
            print(f"{k_}: {v}")
        return 0

    if args.cmd == "dump":
        nodes = ui.dump()
        for n in nodes:
            if args.text is None or args.text in (n.text + n.desc):
                print(_node_line(n))
        if args.out:
            Path(args.out).write_text("\n".join(_node_line(n) for n in nodes), encoding="utf-8")
        return 0

    if args.cmd == "find":
        for n in ui.find(text=args.text, desc=args.desc, exact=args.exact, clickable=None):
            print(_node_line(n))
        return 0

    if args.cmd == "tap-text":
        ok = ui.tap_text(args.text, desc=args.desc, exact=args.exact, timeout=args.timeout)
        print("tapped" if ok else "NOT FOUND", file=sys.stderr)
        return 0 if ok else 1

    if args.cmd == "tap":
        client.tap(args.x, args.y)
        return 0

    if args.cmd == "type":
        ui.type_text(args.text, clear_first=args.clear)
        return 0

    if args.cmd == "key":
        client.keyevent(args.code)
        return 0

    if args.cmd == "wait":
        node = ui.wait_for(args.text, desc=args.desc, timeout=args.timeout)
        if node is None:
            print("timeout", file=sys.stderr)
            return 1
        print(_node_line(node))
        return 0

    if args.cmd == "shot":
        local = client.screen.screenshot_pull(
            local_path=str(Path(args.file).parent),
            filename=Path(args.file).name,
        )
        print(local)
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
