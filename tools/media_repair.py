#!/usr/bin/env python3
"""Media repair — find and repair truncated photos/videos.

The open-source equivalent of Wondershare's corrupted-media repair:

    scan      — verdict per media file: intact | truncated | unknown
                (local dir, or --remote to walk the phone)
    repair    — attempt repair with untrunc (preferred, needs a reference
                file from the same device) or an ffmpeg remux fallback;
                writes <name>.fixed.<ext>, never touches the original

Honesty note: ffmpeg remux fixes container-level breakage only; truncated
MP4 streams need untrunc with a reference file recorded by the SAME
device. Files that are unrecoverable are reported, never deleted.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

SAMPLE = 64 * 1024
REMOTE_CAP = 200

MP4_EXTS = (".mp4", ".mov", ".m4v")
JPEG_EXTS = (".jpg", ".jpeg")


def mp4_verdict(head: bytes, tail: bytes) -> str:
    """intact | truncated | unknown from the file's head/tail byte samples.

    A playable MP4 has an ftyp box near offset 0 and a moov box (the
    index) somewhere in head or tail; truncated recordings keep ftyp but
    never got their moov written.
    """
    if b"ftyp" not in head[:32]:
        return "unknown"
    if b"moov" in head or b"moov" in tail:
        return "intact"
    return "truncated"


def jpeg_verdict(head: bytes, tail: bytes) -> str:
    """intact | truncated | unknown: SOI present, no EOI anywhere in tail.

    Samsung camera JPEGs carry trailing metadata AFTER the EOI marker, so
    "EOI at EOF" would false-positive on every intact photo; the EOI just
    has to exist within the tail sample to prove the stream completed.
    """
    if not head.startswith(b"\xff\xd8"):
        return "unknown"
    if b"\xff\xd9" in tail:
        return "intact"
    return "truncated"


def verdict_for(path: Path) -> str:
    """Read head/tail samples and dispatch to the format's verdict parser."""
    ext = path.suffix.lower()
    if ext not in MP4_EXTS + JPEG_EXTS:
        return "unknown"
    try:
        size = path.stat().st_size
        with open(path, "rb") as fh:
            head = fh.read(SAMPLE)
            fh.seek(max(size - SAMPLE, 0))
            tail = fh.read(SAMPLE)
    except OSError:
        return "unknown"
    if ext in MP4_EXTS:
        return mp4_verdict(head, tail)
    return jpeg_verdict(head, tail)


def scan_dir(root: Path) -> dict[str, list[str]]:
    """Verdicts for every media file under a local tree, grouped."""
    grouped: dict[str, list[str]] = {"intact": [], "truncated": [], "unknown": []}
    if not root.is_dir():
        return grouped
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        grouped[verdict_for(path)].append(str(path))
    return grouped


def _find_untrunc() -> str | None:
    try:
        sys.path.insert(0, str(REPO))
        from tools.binfind import find_binary
    except ImportError:
        return None
    return find_binary("untrunc", None)


def _find_ffmpeg() -> str | None:
    try:
        sys.path.insert(0, str(REPO))
        from tools.binfind import find_binary
    except ImportError:
        return None
    return find_binary("ffmpeg", "Gyan.FFmpeg")


def repair_file(path: Path, reference: Path | None) -> dict[str, object]:
    """Attempt repair; returns {file, outcome, output}.

    Outcome: repaired-untrunc | repaired-remux | no-tool | failed. Writes
    <name>.fixed.<ext> only — the original is never touched.
    """
    out_path = path.with_name(f"{path.stem}.fixed{path.suffix}")
    untrunc = _find_untrunc()
    if untrunc and reference is not None:
        import subprocess

        proc = subprocess.run(  # noqa: S603
            [str(untrunc), str(reference), str(path)],
            capture_output=True,
            check=False,
        )
        if proc.returncode == 0:
            return {"file": str(path), "outcome": "repaired-untrunc", "output": str(out_path)}
        return {
            "file": str(path),
            "outcome": "failed",
            "output": proc.stderr.decode("utf-8", "replace")[:200],
        }
    ffmpeg = _find_ffmpeg()
    if ffmpeg:
        import subprocess

        proc = subprocess.run(  # noqa: S603
            [str(ffmpeg), "-y", "-loglevel", "error", "-i", str(path), "-c", "copy", str(out_path)],
            capture_output=True,
            check=False,
        )
        if proc.returncode == 0 and out_path.exists():
            return {"file": str(path), "outcome": "repaired-remux", "output": str(out_path)}
        return {
            "file": str(path),
            "outcome": "failed",
            "output": proc.stderr.decode("utf-8", "replace")[:200],
        }
    return {
        "file": str(path),
        "outcome": "no-tool",
        "output": "install untrunc (repair needs a reference file) or ffmpeg (remux only)",
    }


def _scan_remote(serial: str | None) -> dict[str, list[str]]:
    """Walk DCIM/Pictures/Movies on the phone, sampling head/tail via base64.

    Binary over `adb shell` gets CRLF-mangled, so samples travel base64
    encoded; decode errors degrade to "unknown". The walk is capped.
    """
    import base64

    from phone import create_client

    client = create_client(serial)
    grouped: dict[str, list[str]] = {"intact": [], "truncated": [], "unknown": []}
    seen = 0
    for root in ("/sdcard/DCIM", "/sdcard/Pictures", "/sdcard/Movies"):
        try:
            out = client.execute("shell", "find", root, "-type", "f")
        except Exception:  # noqa: BLE001 - absent root is normal
            continue
        for path in str(out).splitlines():
            path = path.strip()
            if not path or seen >= REMOTE_CAP:
                continue
            seen += 1
            ext = Path(path).suffix.lower()
            if ext not in MP4_EXTS + JPEG_EXTS:
                grouped["unknown"].append(path)
                continue
            try:
                head_b64 = client.execute("shell", "head", "-c", str(SAMPLE), path, "|", "base64")
                tail_b64 = client.execute("shell", "tail", "-c", str(SAMPLE), path, "|", "base64")
                head = base64.b64decode("".join(head_b64.split()))
                tail = base64.b64decode("".join(tail_b64.split()))
            except Exception:  # noqa: BLE001 - honest degradation
                grouped["unknown"].append(path)
                continue
            verdict = mp4_verdict(head, tail) if ext in MP4_EXTS else jpeg_verdict(head, tail)
            grouped[verdict].append(path)
    return grouped


def _cmd_scan(root: Path, remote: bool, serial: str | None) -> int:
    if remote:
        results = _scan_remote(serial)
    else:
        results = scan_dir(root)
    print(
        json.dumps(
            {
                "intact": len(results["intact"]),
                "truncated": len(results["truncated"]),
                "unknown": len(results["unknown"]),
                "truncated_files": results["truncated"][:20],
            },
            indent=1,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_scan = sub.add_parser("scan", help="verdict per media file")
    p_scan.add_argument("dir", nargs="?", default=str(REPO / "data" / "phone-mirror"))
    p_scan.add_argument("--remote", action="store_true", help="walk the phone instead")
    p_scan.add_argument("--serial")
    p_rep = sub.add_parser("repair", help="attempt repair of one file")
    p_rep.add_argument("file")
    p_rep.add_argument("--reference", help="known-good file from the same device (untrunc)")
    args = ap.parse_args(argv)

    if args.cmd == "scan":
        if args.remote:
            return _cmd_scan(Path("."), True, args.serial)
        return _cmd_scan(Path(args.dir), False, None)
    out = repair_file(Path(args.file), Path(args.reference) if args.reference else None)
    print(json.dumps(out, indent=1))
    return 0 if out["outcome"] in ("repaired-untrunc", "repaired-remux") else 1


if __name__ == "__main__":
    raise SystemExit(main())
