"""Retire the legacy OneDrive tree once the canonical repo is fully authoritative.

The repo was relocated to C:\\dev\\galaxy-s22-toolkit; the old tree at
CrossDevice\\Galaxy S22+ (2) is divergent history plus 8.9 GB of pulled phone
data. This tool retires it safely:

- DRY RUN (default): classifies every file, verifies the canonical repo is
  clean and pushed, and prints the exact plan.
- --execute: moves the phone-mirror data and stray personal files into the
  canonical tree, then deletes the legacy tree EXCEPT harness state
  (.zcode/.mimosa/.glm-hammer) that live tooling may still be using.
- --execute --all: also removes the harness state (run from a fresh
  terminal, never while a session is attached to that tree).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

CANONICAL = Path(r"C:\dev\galaxy-s22-toolkit")
LEGACY = Path(r"C:\Users\tbaltzakis\CrossDevice\Galaxy S22+ (2)")

# Harness/session state that must survive --execute (only --all removes it)
HARNESS_DIRS = {".zcode", ".mimosa", ".glm-hammer"}

# Personal files from the legacy root worth keeping
PRESERVE_ROOT_FILES = (
    "micro1-report.md",
    "micro1-interview-prep.html",
    "dashboard-verification.png",
)

# Runtime/user-data directories moved (same volume -> rename) into canonical
MOVE_DIRS = ("data",)

SKIP_SCAN = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mimy_cache",
    ".mypy_cache",
    "node_modules",
}


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


def _canonical_is_pushed() -> tuple[bool, str]:
    try:
        status = _git(["status", "--porcelain", "-b"], CANONICAL).strip()
        dirty = [
            line for line in status.splitlines() if line.startswith((" M", "M ", "??", "A ", "D "))
        ]
        if dirty:
            return False, f"canonical working tree dirty: {dirty[:5]}"
        ahead = [line for line in status.splitlines() if "ahead" in line]
        if ahead:
            return False, f"canonical not fully pushed: {ahead[0]}"
        return True, "canonical clean and synced"
    except subprocess.CalledProcessError as exc:
        return False, f"git failed in canonical: {exc.stderr.strip()[:120]}"


def _cwd_inside(target: Path) -> bool:
    try:
        Path.cwd().resolve().relative_to(target.resolve())
        return True
    except ValueError:
        return False


def _walk(root: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_SCAN]
        for f in filenames:
            p = Path(dirpath) / f
            rel = str(p.relative_to(root)).replace("\\", "/")
            try:
                out[rel] = p.stat().st_size
            except OSError:
                continue
    return out


def plan(legacy: Path = LEGACY, canonical: Path = CANONICAL) -> dict[str, Any]:
    """Classify the legacy tree into moves, preserves and deletions."""
    legacy_files = _walk(legacy)
    canonical_files = set(_walk(canonical))

    moves: dict[str, Path] = {}
    preserves: dict[str, Path] = {}
    delete_count = 0
    delete_bytes = 0

    for rel, size in legacy_files.items():
        if any(rel.startswith(f"{d}/") for d in MOVE_DIRS):
            moves[rel] = legacy / rel
        elif rel in PRESERVE_ROOT_FILES:
            preserves[rel] = legacy / rel
        else:
            delete_count += 1
            delete_bytes += size

    # Root-level personal files
    for name in PRESERVE_ROOT_FILES:
        p = legacy / name
        if p.is_file() and name not in preserves:
            preserves[name] = p

    return {
        "legacy": legacy,
        "canonical": canonical,
        "total_files": len(legacy_files),
        "total_bytes": sum(legacy_files.values()),
        "moves": moves,
        "preserves": preserves,
        "delete_count": delete_count,
        "delete_bytes": delete_bytes,
        "canonical_files": canonical_files,
    }


def _hydrate(src: Path) -> bool:
    """Force the OneDrive provider to download a cloud placeholder."""
    try:
        with open(src, "rb") as f:
            f.read(1)
        return True
    except OSError:
        return False


def _move_one(src: Path, dst: Path) -> str | None:
    """Best-effort same-volume move; hydrates cloud placeholders first.

    Returns None on success, or a skip reason (WinError 362: the file is a
    cloud-only placeholder and the provider refused to hydrate it).
    """
    try:
        os.replace(src, dst)
        return None
    except OSError as exc:
        if getattr(exc, "winerror", None) != 362:
            raise
        if not _hydrate(src):
            return f"cloud-only placeholder, provider would not hydrate ({exc.strerror})"
        try:
            os.replace(src, dst)
            return None
        except OSError as exc2:
            return f"still unmovable after hydration ({exc2.strerror})"


def _move_tree(src_dir: Path, dst_root: Path) -> tuple[int, list[tuple[str, str]]]:
    """Move src_dir/<rel> into dst_root/<rel> (same-volume rename), merging.

    Never aborts the batch: unmovable cloud placeholders are reported.
    """
    moved = 0
    skipped: list[tuple[str, str]] = []
    for dirpath, _dirnames, filenames in os.walk(src_dir):
        rel_dir = Path(dirpath).relative_to(src_dir)
        (dst_root / rel_dir).mkdir(parents=True, exist_ok=True)
        for f in filenames:
            src = Path(dirpath) / f
            dst = dst_root / rel_dir / f
            if dst.exists():
                continue  # canonical copy wins; legacy data is older
            reason = _move_one(src, dst)
            if reason is None:
                moved += 1
            else:
                skipped.append((str(Path(src_dir).name / rel_dir / f), reason))
    return moved, skipped


def _rmtree_except(root: Path, keep: set[str]) -> list[str]:
    removed = []
    for entry in sorted(root.iterdir()):
        if entry.name in keep:
            continue
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry, ignore_errors=True)
        else:
            try:
                entry.unlink()
            except OSError:
                pass
        removed.append(entry.name)
    return removed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--execute", action="store_true", help="perform the retirement (default: dry run)"
    )
    ap.add_argument(
        "--all",
        action="store_true",
        help="with --execute: also remove harness state (.zcode/.mimosa/.glm-hammer)",
    )
    ap.add_argument("--legacy", type=str, default=str(LEGACY), help="legacy tree path")
    args = ap.parse_args()

    legacy = Path(args.legacy)
    if not legacy.is_dir():
        print(f"Legacy tree not found: {legacy}")
        return 0
    if not CANONICAL.is_dir():
        print(f"Canonical tree missing: {CANONICAL}")
        return 1
    if _cwd_inside(legacy):
        print("REFUSING: current working directory is inside the legacy tree.")
        print("Run this from a directory outside it (e.g. C:\\dev\\galaxy-s22-toolkit).")
        return 1
    ok, why = _canonical_is_pushed()
    if not ok:
        print(f"REFUSING: {why}")
        return 1

    p = plan(legacy)
    gb = p["total_bytes"] / 1e9
    print(f"Legacy tree : {legacy}")
    print(f"Files       : {p['total_files']} ({gb:.1f} GB)")
    print(f"Move to canonical data/legacy-mirror/: {len(p['moves'])} files (data/)")
    print(f"Preserve    : {len(p['preserves'])} files -> {CANONICAL / 'data' / 'legacy-archive'}")
    for name in sorted(p["preserves"]):
        print(f"  - {name}")
    print(f"Delete      : {p['delete_count']} files ({p['delete_bytes'] / 1e6:.1f} MB)")
    keep: set[str] = HARNESS_DIRS if not args.all else set()
    print(f"Harness kept: {sorted(keep) if keep else 'none (--all)'}")

    if not args.execute:
        print("\nDRY RUN — nothing changed. Re-run with --execute to apply.")
        print("Add --all only from a fresh terminal after this session ends.")
        return 0

    # 1) Move user data
    dst = CANONICAL / "data" / "legacy-mirror"
    dst.mkdir(parents=True, exist_ok=True)
    moved, cloud_skipped = _move_tree(legacy / "data", dst)
    print(f"Moved data/ : {moved} files -> {dst}")
    if cloud_skipped:
        report = CANONICAL / "data" / "legacy-archive" / "SKIPPED-CLOUD-FILES.txt"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(
            "".join(f"{path}\t{reason}\n" for path, reason in cloud_skipped),
            encoding="utf-8",
        )
        print(
            f"Cloud-only  : {len(cloud_skipped)} files could not be moved while "
            f"the OneDrive provider refuses hydration — listed in {report}. "
            "They remain in the legacy tree (deleting placeholders is safe; "
            "the cloud copies survive)."
        )

    # 2) Preserve personal files
    arch = CANONICAL / "data" / "legacy-archive"
    arch.mkdir(parents=True, exist_ok=True)
    for name, src in p["preserves"].items():
        if name in ("micro1-report.md", "micro1-interview-prep.html", "dashboard-verification.png"):
            shutil.copy2(src, arch / name)
            print(f"Preserved   : {name} -> {arch / name}")

    # 3) Delete the rest
    removed = _rmtree_except(legacy, keep)
    print(f"Deleted     : {len(removed)} top-level entries; kept: {sorted(keep)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
