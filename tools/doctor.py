#!/usr/bin/env python3
"""Environment doctor for the Galaxy S22+ toolkit.

Checks the environment-bug class this repo keeps hitting: OneDrive
read-only flags, mangled U+F03A junk files, adb connectivity, WSL
distro references, git hooks, and the dashboard container.

Usage:
    python tools/doctor.py            # report
    python tools/doctor.py --fix      # also apply safe fixes (attr clear)
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tools.binfind import find_binary  # noqa: E402
from tools.clean_path_artifacts import find_artifacts  # noqa: E402
from tools.fix_onedrive_attrs import clear_flags, find_readonly  # noqa: E402

failures = 0


def check(name: str, ok: bool, detail: str) -> None:
    global failures
    print(f"{'OK  ' if ok else 'FAIL'}  {name}: {detail}")
    if not ok:
        failures += 1


def check_adb() -> None:
    adb = shutil.which("adb") or r"C:\Users\tbaltzakis\Android\Sdk\platform-tools\adb.exe"
    if not shutil.which("adb") and not Path(adb).exists():
        check("adb", False, "not found in PATH or SDK location")
        return
    try:
        out = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=10).stdout
        n = sum(
            1 for ln in out.splitlines()[1:] if ln.strip() and "device" in ln and "List" not in ln
        )
        check("adb", n > 0, f"{n} device(s) attached")
    except (OSError, subprocess.TimeoutExpired) as exc:
        check("adb", False, str(exc))


def check_onedrive() -> None:
    n = len(find_readonly(REPO))
    check(
        "onedrive-flags",
        n == 0,
        f"{n} read-only flagged file(s)" + (" (run with --fix)" if n else ""),
    )


def check_junk() -> None:
    n = len(find_artifacts(REPO))
    check("junk-files", n == 0, f"{n} U+F03A artifact(s)" + (" (run --fix)" if n else ""))


def check_hooks() -> None:
    hook = REPO / ".git" / "hooks" / "pre-commit"
    check(
        "git-hooks",
        hook.exists(),
        "pre-commit installed" if hook.exists() else "run tools/install_git_hooks.py",
    )


def check_wsl() -> None:
    """Read-only report: installed distros vs any the editor references."""
    try:
        raw = subprocess.run(
            ["wsl.exe", "--list", "--verbose"], capture_output=True, timeout=15
        ).stdout.decode("utf-16-le", errors="replace")
    except (OSError, subprocess.TimeoutExpired) as exc:
        check("wsl", True, f"skipped ({exc})")
        return
    lines = [ln.strip() for ln in raw.replace("\x00", "").splitlines() if ln.strip()]
    names = [
        ln.split()[1] if ln.split()[0] == "*" else ln.split()[0] for ln in lines[1:] if ln.split()
    ]
    check(
        "wsl",
        True,
        f"installed: {', '.join(names) or 'none'} (editor distro refs not auto-fixable)",
    )


def check_backup() -> None:
    try:
        r = subprocess.run(
            [sys.executable, str(REPO / "tools" / "backup_metrics_db.py"), "--check"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        detail = (r.stdout or r.stderr).strip().splitlines()
        check("metrics-backup", r.returncode == 0, detail[-1] if detail else "no output")
    except (OSError, subprocess.TimeoutExpired) as exc:
        check("metrics-backup", False, str(exc))


def check_container() -> None:
    try:
        out = subprocess.run(
            ["docker", "compose", "ps", "--format", "{{.Name}}: {{.Status}}"],
            capture_output=True,
            text=True,
            timeout=20,
            cwd=REPO,
        ).stdout.strip()
        check("dashboard", bool(out), out or "container not running (docker compose up -d --build)")
    except (OSError, subprocess.TimeoutExpired) as exc:
        check("dashboard", False, str(exc))


def check_mobile_suite() -> None:
    """Full Mobile Suite external pillars: scrcpy, Heimdall, libimobiledevice.

    Missing tools are reported with the exact winget/install line so the fix
    is one paste away. Absence is advisory (each suite feature degrades to an
    honest 'tool not installed' message) but still counted so doctor surfaces
    the gap.
    """
    probes = {
        "scrcpy": ("scrcpy", "Genymobile.scrcpy", "winget install Genymobile.scrcpy"),
        "heimdall": (
            "heimdall",
            "BenjaminDobell.Heimdall",
            "winget install BenjaminDobell.Heimdall",
        ),
        "idevice_id": (
            "idevice_id",
            None,
            "install libimobiledevice (https://libimobiledevice.org)",
        ),
    }
    for label, (binary, winget_id, install) in probes.items():
        path = find_binary(binary, winget_id)
        if path:
            check(f"mobile:{label}", True, path)
        else:
            check(f"mobile:{label}", False, f"not installed — {install}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fix", action="store_true", help="apply safe fixes")
    args = parser.parse_args()
    print(f"doctor: {REPO}")
    check_adb()
    check_onedrive()
    check_junk()
    check_hooks()
    check_backup()
    check_wsl()
    check_container()
    check_mobile_suite()
    if args.fix:
        junk = find_artifacts(REPO)
        for p in junk:
            try:
                p.unlink()
            except OSError as exc:
                print(f"  junk delete failed: {exc}")
        cleared = clear_flags(find_readonly(REPO))
        print(f"--fix applied: {cleared} attr(s) cleared, {len(junk)} junk deleted")
    print("result:", "PASS" if failures == 0 else f"{failures} check(s) failed")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
