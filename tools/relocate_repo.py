#!/usr/bin/env python3
"""Migrate the toolkit out of the OneDrive-synced path (dry-run default).

OneDrive re-applies read-only flags to repo files (breaking edits and
commits). The durable fix is living outside the synced tree. This tool
performs a git-clone-based migration so history stays intact:

  1. clone this repo to --target (default C:\\dev\\galaxy-s22-toolkit)
  2. copy runtime state the clone cannot carry: .env, logs/, reports/,
     backups/, diagnostics/reports/
  3. re-register the three \\Phone Toolkit\\ scheduled tasks with the new
     WorkingDirectory
  4. print the finish-by-hand list (pip -e reinstall, docker compose
     down/up from the new path, delete the old tree)

Usage:
    python tools/relocate_repo.py                 # plan only (no changes)
    python tools/relocate_repo.py --execute       # perform the migration
    python tools/relocate_repo.py --target D:\\code\\s22toolkit
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = Path(r"C:\dev\galaxy-s22-toolkit")
RUNTIME_ITEMS = [".env", "logs", "reports", "backups", "diagnostics/reports"]
TASKS = [
    "Galaxy S22+ Diagnostics",
    "Galaxy S22+ Metrics Backup",
    "Galaxy S22+ Insights Report",
]


def plan(target: Path) -> list[str]:
    return [
        f"clone   : {REPO}  ->  {target}",
        f"copy    : {', '.join(RUNTIME_ITEMS)}",
        f"re-task : {', '.join(TASKS)} (new WorkingDirectory={target})",
        "manual  : pip install -e <target>/phone-lib",
        "manual  : docker compose down (old) && docker compose up -d --build (new)",
        "manual  : verify with python tools/doctor.py, then delete the old tree",
    ]


def under_onedrive(path: Path) -> bool:
    return "onedrive" in str(path).lower()


def run(cmd: list[str], cwd: Path | None = None) -> bool:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  FAILED: {' '.join(cmd)}\n  {r.stderr.strip()}", file=sys.stderr)
    return r.returncode == 0


def execute(target: Path) -> int:
    if target.exists() and any(target.iterdir()):
        print(f"refusing: target exists and is not empty: {target}", file=sys.stderr)
        return 1
    if under_onedrive(target):
        print(f"refusing: target is inside an OneDrive-synced path: {target}", file=sys.stderr)
        return 1

    print(f"cloning to {target} ...")
    target.parent.mkdir(parents=True, exist_ok=True)
    if not run(["git", "clone", str(REPO), str(target)]):
        return 1

    for item in RUNTIME_ITEMS:
        src = REPO / item
        if not src.exists():
            continue
        dst = target / item
        print(f"copying {item} ...")
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    ps = (
        "$tasks = @(" + ",".join(f"'{t}'" for t in TASKS) + ");"
        f"$old = '{REPO}'; $new = '{target}';"
        "foreach ($t in $tasks) {"
        "  $def = Get-ScheduledTask -TaskPath '\\Phone Toolkit\\' -TaskName $t"
        "    -ErrorAction SilentlyContinue; if (-not $def) { continue };"
        "  $act = $def.Actions[0]; $act.WorkingDirectory = $new;"
        "  Set-ScheduledTask -TaskPath '\\Phone Toolkit\\' -TaskName $t"
        "    -Action $act | Out-Null; Write-Output ('re-tasked ' + $t)"
        "}"
    )
    print("re-registering scheduled tasks ...")
    run(["powershell", "-NoProfile", "-Command", ps])

    print("\nMigration done. Finish by hand:")
    for line in plan(target)[3:]:
        print(" ", line)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", default=str(DEFAULT_TARGET))
    parser.add_argument(
        "--execute", action="store_true", help="perform the migration (default: plan only)"
    )
    args = parser.parse_args(argv)
    target = Path(args.target)

    for line in plan(target):
        print(line)
    if not args.execute:
        print("\n(dry-run: pass --execute to perform)")
        return 0
    if under_onedrive(REPO):
        print(
            "note: source is OneDrive-synced; keep it until the new tree "
            "is verified, then delete it"
        )
    return execute(target)


if __name__ == "__main__":
    raise SystemExit(main())
