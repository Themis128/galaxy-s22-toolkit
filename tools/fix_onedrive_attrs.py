#!/usr/bin/env python3
"""Clear Windows read-only flags OneDrive keeps re-applying in this repo.

OneDrive's sync engine re-flags files (including .git internals like
COMMIT_EDITMSG) read-only within seconds, which breaks edits and commits.
The durable fix is moving the repo out of the synced path; until then,
run this before batch file operations or let the pre-commit hook handle
the commit path.

Usage:
    python tools/fix_onedrive_attrs.py            # clear flags
    python tools/fix_onedrive_attrs.py --check    # report only, change nothing
"""

from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path

SKIP_DIRS = {"node_modules", ".venv", "venv", "__pycache__"}


def find_readonly(root: Path) -> list[Path]:
    """Return repo files carrying the Windows read-only attribute."""
    flagged: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            p = Path(dirpath) / name
            try:
                attrs = p.stat().st_file_attributes
            except (OSError, AttributeError):  # not Windows, or vanished
                continue
            if attrs & stat.FILE_ATTRIBUTE_READONLY:
                flagged.append(p)
    return flagged


def clear_flags(files: list[Path]) -> int:
    """Clear the read-only attribute; returns how many were cleared."""
    cleared = 0
    for p in files:
        try:
            os.chmod(p, stat.S_IWRITE)
            cleared += 1
        except OSError as exc:
            print(f"  could not clear {p}: {exc}", file=sys.stderr)
    return cleared


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "root",
        nargs="?",
        default=str(Path(__file__).resolve().parents[1]),
        help="repo root (default: this repo)",
    )
    parser.add_argument("--check", action="store_true", help="report only")
    args = parser.parse_args(argv)

    root = Path(args.root)
    flagged = find_readonly(root)
    print(f"{len(flagged)} read-only flagged file(s) under {root}")
    if args.check or not flagged:
        return 0
    cleared = clear_flags(flagged)
    print(f"cleared {cleared}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
