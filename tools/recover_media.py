#!/usr/bin/env python3
"""Data recovery — the open-source Wondershare Data Recovery equivalent.

Tier A (no root): pull trash/deleted media that Android still keeps on
device (MediaStore .trashed-* dirs under common roots).

Tier B (root-gated): pull + decrypt the WhatsApp message-store backup
(crypt12/14/15 via wa-crypt-tools) and export chats to JSON. Requires the
WhatsApp key — extracted via root (su) with explicit confirmation. Deep
unallocated-space scans are documented in rooting/RUNBOOK.md and are NOT
automated here (raw block I/O is too risky).

Usage:
    python tools/recover_media.py trash [--serial S]   # Tier A
    python tools/recover_media.py whatsapp [--serial S] [--confirm-key]  # Tier B
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
RECOVERED = REPO / "data" / "recovered"
if __name__ == "__main__":
    sys.path.insert(0, str(REPO))

try:
    from phone import create_client
    from phone.exceptions import PhoneError
    from phone.root import RootModule
except ImportError:  # pragma: no cover
    create_client = None  # type: ignore[assignment]

TRASH_DIRS = (
    "/sdcard/DCIM/.trashed",
    "/sdcard/Download/.trashed",
    "/sdcard/Pictures/.trashed",
    "/sdcard/Movies/.trashed",
    "/sdcard/Download/.Trash",
)
TRASHED_NAME_RE = re.compile(r"^\.(trashed-\d+[-~])(?P<name>.+)$")

WHATSAPP_DB_CANDIDATES = (
    "/sdcard/Android/media/com.whatsapp/WhatsApp/Databases/msgstore.db.crypt15",
    "/sdcard/Android/media/com.whatsapp/WhatsApp/Databases/msgstore.db.crypt14",
    "/sdcard/Android/media/com.whatsapp/WhatsApp/Databases/msgstore.db.crypt12",
    "/sdcard/Android/media/com.whatsapp.w4b/WhatsApp/Databases/msgstore.db.crypt15",
    "/sdcard/Android/media/com.whatsapp.w4b/WhatsApp/Databases/msgstore.db.crypt14",
)


def _client(serial: str | None = None) -> Any:
    import yaml

    with open(REPO / "diagnostics" / "config.yaml", encoding="utf-8") as f:
        device_cfg = (yaml.safe_load(f) or {}).get("device", {})
    wireless = device_cfg.get("wireless_adb") or None
    if wireless:
        wireless = {**wireless, "preferred_serial": device_cfg.get("serial")}
    return create_client(serial, wireless=wireless)


def parse_trashed_name(name: str) -> str | None:
    """Original filename of a MediaStore trash entry (pure; unit-tested)."""
    m = TRASHED_NAME_RE.match(name)
    return m.group("name") if m else None


def _ls(c: Any, path: str) -> list[str]:
    out = c.execute("shell", "ls", "-A1", path)
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def recover_trash(c: Any, dest_root: Path) -> list[dict[str, str]]:
    """Pull every trash item the device still keeps (Tier A, no root)."""
    dest_root.mkdir(parents=True, exist_ok=True)
    pulled: list[dict[str, str]] = []
    for root_dir in TRASH_DIRS:
        try:
            names = _ls(c, root_dir)
        except PhoneError:
            continue
        for name in names:
            remote = f"{root_dir}/{name}"
            original = parse_trashed_name(name) or name
            dest = dest_root / original
            try:
                c.pull(remote, str(dest))
                pulled.append({"remote": remote, "recovered_as": str(dest)})
            except PhoneError as exc:
                pulled.append({"remote": remote, "error": str(exc)[:120]})
    return pulled


def _decrypt_available() -> bool:
    try:
        import wa_crypt_tools  # type: ignore[import-not-found]  # noqa: F401

        return True
    except ImportError:
        return False


def recover_whatsapp(c: Any, dest_root: Path, confirm_key: bool) -> dict[str, Any]:
    """Tier B: root-gated WhatsApp backup pull + decrypt + export."""
    report: dict[str, Any] = {"tier": "B (root-gated)", "steps": []}
    root = RootModule(c)
    if not root.is_rooted():
        report["steps"].append(
            "root: NOT AVAILABLE — Tier B requires root (Knox warning: unlocking "
            "the bootloader trips the eFuse permanently; see rooting/RUNBOOK.md)"
        )
        report["status"] = "requires_root"
        return report
    report["steps"].append("root: available")

    db_remote = None
    for cand in WHATSAPP_DB_CANDIDATES:
        try:
            if _ls(c, str(Path(cand).parent)).count(Path(cand).name) > 0:
                db_remote = cand
                break
        except PhoneError:
            continue
    if db_remote is None:
        report["steps"].append("backup: no msgstore crypt backup found on device")
        report["status"] = "no_backup"
        return report
    report["steps"].append(f"backup: found {db_remote}")

    if not confirm_key:
        report["steps"].append(
            "key: NOT extracted — re-run with --confirm-key to read /data/data/com.whatsapp*/files/key via root (explicit confirmation required)"
        )
        report["status"] = "needs_confirm"
        return report

    key = root.run_privileged(
        "cat /data/data/com.whatsapp/files/key /data/data/com.whatsapp.w4b/files/key 2>/dev/null",
        confirm=True,
    ).strip()
    key = key.splitlines()[0].strip() if key else ""
    if not key:
        report["steps"].append("key: extraction failed (no key file readable via su)")
        report["status"] = "key_failed"
        return report
    report["steps"].append("key: extracted via root")

    if not _decrypt_available():
        report["steps"].append("decrypt: wa-crypt-tools not installed — pip install wa-crypt-tools")
        report["status"] = "decryptor_missing"
        return report

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = dest_root / "whatsapp"
    out_dir.mkdir(parents=True, exist_ok=True)
    db_local = out_dir / f"msgstore-{stamp}.db.crypt15"
    c.pull(db_remote, str(db_local))
    plain = out_dir / f"msgstore-{stamp}.db"
    wadecrypt = shutil.which("wadecrypt")
    cmd = (
        [wadecrypt, key, str(db_local), str(plain)]
        if wadecrypt
        else [sys.executable, "-m", "wa_crypt_tools", key, str(db_local), str(plain)]
    )
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not plain.exists():
        report["steps"].append(f"decrypt: failed — {(proc.stderr or proc.stdout).strip()[:160]}")
        report["status"] = "decrypt_failed"
        return report
    report["steps"].append(f"decrypt: OK -> {plain.name}")

    import sqlite3

    conn = sqlite3.connect(str(plain))
    try:
        rows = conn.execute(
            "SELECT key_raw_jid, timestamp, text FROM messages ORDER BY timestamp DESC LIMIT 5000"
        ).fetchall()
    finally:
        conn.close()
    export = out_dir / f"chats-{stamp}.json"
    export.write_text(
        json.dumps([{"chat": r[0], "timestamp": r[1], "text": r[2]} for r in rows], indent=1),
        encoding="utf-8",
    )
    report["steps"].append(f"export: {len(rows)} messages -> {export.name}")
    report["status"] = "ok"
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_t = sub.add_parser("trash", help="Tier A: pull trash/deleted media (no root)")
    p_t.add_argument("--serial")
    p_w = sub.add_parser("whatsapp", help="Tier B: WhatsApp backup decrypt (root-gated)")
    p_w.add_argument("--serial")
    p_w.add_argument("--confirm-key", action="store_true")
    args = parser.parse_args(argv)

    if create_client is None:
        print("phone-lib not importable")
        return 1
    c = _client(args.serial)

    if args.cmd == "trash":
        items = recover_trash(c, RECOVERED)
        ok = sum(1 for i in items if "recovered_as" in i)
        print(f"Tier A: {ok} item(s) recovered to {RECOVERED} ({len(items) - ok} skipped)")
        for i in items[:10]:
            print(" ", i.get("recovered_as") or i.get("error"), "<-", i["remote"])
        return 0

    report = recover_whatsapp(c, RECOVERED, args.confirm_key)
    print(f"Tier B ({report['status']}):")
    for s in report["steps"]:
        print("  -", s)
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
