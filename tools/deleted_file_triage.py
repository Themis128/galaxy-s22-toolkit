#!/usr/bin/env python3
"""Deleted-file triage — what is recoverable, and how (read-only).

The open-source equivalent of Wondershare's deleted-file recovery entry
point: an honest triage of recovery candidates before you commit to a
recovery flow.

    scan      — read-only inventory: Samsung trash dirs (file counts +
                bytes), .thumbnails size, DCIM .trashed/.pending overlays
    deep      — root-gated extra pass; on an unrooted phone it says so
                honestly and exits 0

No mutation anywhere: `phone-recover trash` performs the actual recovery;
`phone data-eraser free-space` performs the secure overwrite. Files whose
names start with .trashed- are the Gallery's soft-deleted items.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tools.recover_media import TRASH_DIRS, parse_trashed_name  # noqa: E402

try:
    from phone import create_client
except ImportError:  # pragma: no cover
    create_client = None  # type: ignore[assignment]

N_A = "N/A"


def _probe(client: object, *args: str) -> str:
    """One shell probe; empty string on any error (N/A degradation)."""
    try:
        out = client.execute("shell", *args)  # type: ignore[attr-defined]
        return str(out).strip()
    except Exception:  # noqa: BLE001 - triage must never raise
        return ""


def _trash_count(client: object, trash_dir: str) -> int:
    """Count of soft-deleted (.trashed-*) items in one trash dir."""
    out = _probe(client, "ls", "-A1", trash_dir)
    if not out:
        return 0
    return sum(1 for ln in out.splitlines() if parse_trashed_name(ln.strip()))


def _du_kb(client: object, path: str) -> int | None:
    """Size of a remote dir in KB, or None when unreadable."""
    out = _probe(client, "du", "-sk", path)
    if not out:
        return None
    try:
        return int(out.split()[0])
    except (ValueError, IndexError):
        return None


def triage_lines(trash_counts: dict[str, int], thumb_bytes_kb: int | None) -> list[str]:
    """Deterministic report lines from the raw probe results."""
    lines: list[str] = []
    total = 0
    for trash_dir in sorted(trash_counts):
        count = trash_counts[trash_dir]
        total += count
        marker = f"{count:>5}" if count else "    0"
        lines.append(f"  trash {trash_dir}: {marker} item(s)")
    if thumb_bytes_kb is None:
        lines.append("  thumbnails: N/A")
    else:
        lines.append(f"  thumbnails: {thumb_bytes_kb} KB reclaimable")
    lines.append(f"  TOTAL soft-deleted items: {total}")
    return lines


def cmd_scan(client: object) -> int:
    """Read-only recovery-candidate inventory."""
    print("== Deleted-file triage (read-only) ==")
    trash_counts: dict[str, int] = {}
    for trash_dir in TRASH_DIRS:
        trash_counts[trash_dir] = _trash_count(client, trash_dir)
    thumb_kb = _du_kb(client, "/sdcard/DCIM/.thumbnails")
    for line in triage_lines(trash_counts, thumb_kb):
        print(line)
    print()
    print("Recovery routes:")
    print("  - phone-recover trash     -> pull soft-deleted items back")
    print("  - data eraser free-space  -> secure-overwrite remnants instead")
    return 0


def cmd_deep(client: object) -> int:
    """Root-gated extra pass; honest refusal on unrooted devices."""
    su = _probe(client, "which", "su")
    if not su:
        print(
            "deep triage needs root (raw-partition scan) - this device is "
            "unrooted, so the honest answer is: only the trash/thumbnail "
            "candidates above are reachable. Rooting/ stays S22+-specific "
            "by design; see rooting/ for the rooted workflow."
        )
        return 0
    print("Root detected - deep scan would read raw user data partitions.")
    print("(Not implemented on purpose: partition carving on FBE flash is")
    print(" best-effort theater; the trash route above is the real path.)")
    return 0


def _client(serial: str | None) -> object:
    if create_client is None:
        raise SystemExit("phone-lib not importable")
    import yaml

    with open(REPO / "diagnostics" / "config.yaml", encoding="utf-8") as fh:
        device_cfg = (yaml.safe_load(fh) or {}).get("device", {})
    wireless = device_cfg.get("wireless_adb") or None
    if wireless:
        wireless = {**wireless, "preferred_serial": device_cfg.get("serial")}
    return create_client(serial, wireless=wireless)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("scan", "deep"):
        sub.add_parser(name)
        sub.choices[name].add_argument("--serial")
    args = ap.parse_args(argv)
    if create_client is None:
        print("phone-lib not importable")
        return 1
    client = _client(args.serial)
    if args.cmd == "scan":
        return cmd_scan(client)
    return cmd_deep(client)


if __name__ == "__main__":
    raise SystemExit(main())
