#!/usr/bin/env python3
"""Find and optionally delete mangled path-artifact junk files.

Junk files are named after a full Windows path with the drive colon
replaced by the private-use character U+F03A. The pre-commit hook
(installed by install_git_hooks.py) blocks staging them.

Usage:
    python tools/clean_path_artifacts.py            # dry-run (default)
    python tools/clean_path_artifacts.py --delete   # actually delete
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ARTIFACT_CHAR = "\uf03a"


def find_artifacts(root: Path) -> list[Path]:
    """Return files whose name contains the mangled-path marker char."""
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for name in filenames:
            if ARTIFACT_CHAR in name:
                found.append(Path(dirpath) / name)
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", nargs="?", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--delete", action="store_true", help="delete the junk files")
    args = parser.parse_args(argv)
    found = find_artifacts(Path(args.root))
    if not found:
        print("no mangled path artifacts found")
        return 0
    for p in found:
        print("artifact:", p)
        if args.delete:
            try:
                os.chmod(p, 0o666)
                p.unlink()
            except OSError as exc:
                print("  delete failed:", exc, file=sys.stderr)
    print(len(found), "artifact(s)", "deleted" if args.delete else "found (dry-run)")
    return 1 if not args.delete else 0


if __name__ == "__main__":
    raise SystemExit(main())
