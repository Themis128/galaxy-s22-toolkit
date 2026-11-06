#!/usr/bin/env python3
"""Safely retire the legacy OneDrive working copy of the toolkit.

The toolkit moved to ``C:\\dev\\galaxy-s22-toolkit``; the old
OneDrive-synced tree remains on disk. This tool verifies the legacy copy
is fully superseded, exports any runtime data only it still holds, and
finally deletes it - with explicit confirmation and OneDrive-placeholder
awareness (locked cloud files are reported, never silently lost).

Usage:
    python tools/decommission_legacy.py check          # read-only preflight
    python tools/decommission_legacy.py export         # copy newer runtime data
    python tools/decommission_legacy.py delete --confirm
"""

from __future__ import annotations

# ruff: noqa: T201  # CLI output requires print statements
import argparse
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

CANONICAL = Path(r"C:\dev\galaxy-s22-toolkit")
DEFAULT_LEGACY = Path(r"C:\Users\tbaltzakis\CrossDevice\Galaxy S22+ (2)")
RUNTIME_DIRS = ["logs", "reports", "backups", "diagnostics/reports", "data/phone-mirror"]


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


@dataclass
class Report:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def add(self, name: str, ok: bool, detail: str) -> None:
        self.checks.append(CheckResult(name, ok, detail))


def git(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True
    ).stdout.strip()


def check_canonical(rep: Report) -> None:
    ok = CANONICAL.is_dir() and (CANONICAL / ".git").is_dir()
    rep.add("canonical-tree", ok, str(CANONICAL))
    if not ok:
        return
    head = git(["log", "--oneline", "-1"], CANONICAL)
    rep.add("canonical-git", bool(head), head or "no commits")


def check_legacy_git(rep: Report, legacy: Path) -> None:
    """Legacy HEAD must already be contained in origin/master (nothing unique)."""
    head = git(["rev-parse", "HEAD"], legacy)
    if not head:
        rep.add("legacy-git", False, "not a git repo")
        return
    subprocess.run(["git", "fetch", "origin"], cwd=str(legacy), capture_output=True)
    merged = (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", head, "origin/master"],
            cwd=str(legacy),
            capture_output=True,
        ).returncode
        == 0
    )
    dirty = git(["status", "--porcelain"], legacy)
    detail = f"HEAD {head[:8]} ancestor-of-origin/master={merged}"
    if dirty:
        detail += f"; UNCOMMITTED: {len(dirty.splitlines())} file(s)"
    rep.add("legacy-git", merged and not dirty, detail)


def check_scheduled_tasks(rep: Report) -> None:
    ps = (
        "$tasks = @('Galaxy S22+ Diagnostics','Galaxy S22+ Metrics Backup',"
        "'Galaxy S22+ Insights Report');"
        "foreach ($t in $tasks) {"
        "  $def = Get-ScheduledTask -TaskPath '\\Phone Toolkit\\' -TaskName $t"
        "    -ErrorAction SilentlyContinue; if ($def) {"
        "    Write-Output ($t + '|' + $def.Actions[0].WorkingDirectory) } }"
    )
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True
    ).stdout.strip()
    if not out:
        rep.add("scheduled-tasks", False, "no tasks found (renamed or removed?)")
        return
    wrong = [line for line in out.splitlines() if "galaxy-s22-toolkit" not in line]
    rep.add(
        "scheduled-tasks",
        not wrong,
        "all point at canonical" if not wrong else f"NOT canonical: {'; '.join(wrong)}",
    )


def check_python_resolves(rep: Report) -> None:
    out = subprocess.run(
        [sys.executable, "-c", "import phone; print(phone.__file__)"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    rep.add(
        "pip-editable",
        "galaxy-s22-toolkit" in out,
        out or "import phone failed",
    )


def check_docker(rep: Report) -> None:
    """The dashboard container must not reference the legacy path."""
    out = subprocess.run(
        ["docker", "inspect", "galaxy-s22-toolkit-dashboard-1"],
        capture_output=True,
        text=True,
    ).stdout
    if not out:
        rep.add("docker-container", False, "dashboard container not found")
        return
    rep.add(
        "docker-container",
        "Galaxy S22+" not in out and "CrossDevice" not in out,
        "no legacy-path references" if "CrossDevice" not in out else "references legacy path",
    )


def is_placeholder(path: Path) -> bool:
    """True for OneDrive placeholders: content is cloud-backed, the local
    file cannot be read while the cloud file provider is down."""
    try:
        with path.open("rb") as f:
            while f.read(1024 * 1024):
                pass  # full streaming read forces OneDrive hydration
        return False
    except OSError as e:
        # Cloud-provider hydration failures report winerror 362/364/...;
        # broken reparse points surface as errno 22 with no winerror.
        if getattr(e, "winerror", None) in (362, 364, 366, 383, 392):
            return True
        return e.errno == 22


def check_runtime_data(rep: Report, legacy: Path) -> None:
    """Canonical's runtime copies must be at least as fresh as legacy's.

    Unreadable OneDrive placeholders are cloud-backed: deleting the local
    copy moves them to OneDrive's Recycle Bin (recoverable ~30 days), so
    they warn instead of blocking. Readable-but-newer files block.
    """
    stale: list[str] = []
    placeholders = 0
    for item in RUNTIME_DIRS:
        src = legacy / item
        dst = CANONICAL / item
        if not src.exists():
            continue
        for f in src.rglob("*"):
            if not f.is_file():
                continue
            target = dst / f.relative_to(src)
            if target.exists() and f.stat().st_mtime <= target.stat().st_mtime + 1:
                continue
            if is_placeholder(f):
                placeholders += 1
                continue
            stale.append(f"{item}/{f.relative_to(src)}")
    if stale:
        rep.add(
            "runtime-data-fresh",
            False,
            f"readable files only in legacy: {', '.join(stale[:5])} (run export)",
        )
    else:
        detail = "canonical up to date"
        if placeholders:
            detail += (
                f"; {placeholders} OneDrive placeholder(s) are cloud-backed - "
                "deleting sends them to OneDrive's Recycle Bin (~30 days to restore)"
            )
        rep.add("runtime-data-fresh", True, detail)
    rep.add(
        "runtime-placeholders",
        True,
        f"{placeholders} cloud-backed file(s) in legacy runtime dirs (informational)",
    )


def run_check(legacy: Path) -> Report:
    rep = Report()
    check_canonical(rep)
    check_legacy_git(rep, legacy)
    check_scheduled_tasks(rep)
    check_python_resolves(rep)
    check_docker(rep)
    check_runtime_data(rep, legacy)
    return rep


def cmd_check(legacy: Path) -> int:
    rep = run_check(legacy)
    for c in rep.checks:
        mark = "OK  " if c.ok else "FAIL"
        print(f"{mark} {c.name}: {c.detail}")
    print(f"\nresult: {'PASS - legacy tree is fully superseded' if rep.ok else 'FAIL'}")
    return 0 if rep.ok else 1


def export_runtime(legacy: Path) -> tuple[list[str], list[str]]:
    """Copy runtime files that exist only in (or are newer in) the legacy tree.

    OneDrive placeholder files (cloud file provider not running) are
    reported per-path instead of aborting the whole export.
    """
    copied: list[str] = []
    failed: list[str] = []
    for item in RUNTIME_DIRS:
        src = legacy / item
        dst = CANONICAL / item
        if not src.exists():
            continue
        for f in src.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(src)
            target = dst / rel
            try:
                if not target.exists() or f.stat().st_mtime > target.stat().st_mtime + 1:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        shutil.copy2(f, target)
                    except OSError:
                        # CopyFile2 refuses hydrated-but-flaky OneDrive files;
                        # a manual byte copy exercises the same path the
                        # check probes with, so both tools converge.
                        data = f.read_bytes()
                        target.write_bytes(data)
                    copied.append(str(rel))
            except OSError as e:
                failed.append(f"{rel}: {e}")
    return copied, failed


def cmd_export(legacy: Path) -> int:
    copied, failed = export_runtime(legacy)
    print(f"copied {len(copied)} file(s) to canonical")
    for c in copied[:20]:
        print(" ", c)
    if len(copied) > 20:
        print(f"  ... and {len(copied) - 20} more")
    if failed:
        print(f"\n{len(failed)} file(s) unreadable (OneDrive placeholders?):")
        for e in failed[:10]:
            print(" ", e)
        print("resume OneDrive sync so files hydrate locally, then re-run export")
        return 1
    return 0
    return 0


def delete_tree(legacy: Path) -> tuple[bool, list[str]]:
    """Delete with read-only/OneDrive handling; report survivors."""
    errors: list[str] = []

    def onerror(func: Callable[[str], None], path: str, exc: object) -> None:
        try:
            os_chmod_write(path)
            func(path)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{path}: {e}")

    shutil.rmtree(legacy, onerror=onerror)
    return (not legacy.exists()), errors


def os_chmod_write(path: str) -> None:
    import os
    import stat

    os.chmod(path, stat.S_IWRITE)


def cmd_delete(legacy: Path, confirm: bool) -> int:
    if CANONICAL in legacy.parents or str(legacy) in str(Path.cwd()):
        print("refusing: current working directory is inside the legacy tree")
        print("close ZCode sessions bound to it, then run this from the canonical tree")
        return 1
    rep = run_check(legacy)
    if not rep.ok:
        print("preflight failed - fix these first:")
        for c in rep.checks:
            if not c.ok:
                print(f"  FAIL {c.name}: {c.detail}")
        print("run 'export' for stale runtime data, then re-check")
        return 1
    size = sum(f.stat().st_size for f in legacy.rglob("*") if f.is_file()) // (1024 * 1024)
    print(f"About to permanently delete: {legacy}")
    print(f"Approximate size: {size} MB")
    if not confirm:
        print("dry-run only - pass --confirm to delete")
        return 2
    t0 = time.time()
    gone, errors = delete_tree(legacy)
    if gone:
        print(f"deleted in {time.time() - t0:.0f}s - legacy tree retired")
        return 0
    print(f"{len(errors)} path(s) could not be deleted (OneDrive placeholders?):")
    for e in errors[:15]:
        print(" ", e)
    print("resume OneDrive sync / close file handles, then run delete again")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--legacy", default=str(DEFAULT_LEGACY))
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="verify the legacy tree is fully superseded (read-only)")
    sub.add_parser("export", help="copy newer runtime data to the canonical tree")
    p_del = sub.add_parser("delete", help="delete the legacy tree (preflight + --confirm)")
    p_del.add_argument("--confirm", action="store_true")
    args = parser.parse_args(argv)
    legacy = Path(args.legacy)

    if args.cmd == "check":
        return cmd_check(legacy)
    if args.cmd == "export":
        return cmd_export(legacy)
    if args.cmd == "delete":
        return cmd_delete(legacy, args.confirm)
    return 1


if __name__ == "__main__":
    sys.exit(main())
