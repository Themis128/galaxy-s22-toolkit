#!/usr/bin/env python3
"""Docker Engine watchdog — permanent self-healing for the WSL crash pattern.

Docker Desktop's engine has crashed repeatedly on this machine (WSL
E_UNEXPECTED / VmSwitch reloads on an Insider build). This watchdog runs
from a scheduled task every 15 minutes and:

1. probes the engine pipe (`docker info`);
2. if dead: starts Docker Desktop, waits up to 3 minutes for the engine;
3. brings the toolkit dashboard back up (`docker compose up -d`);
4. appends everything to logs/docker-watchdog.log (capped at 1 MB).

Exit codes: 0 = engine healthy or healed; 1 = still down after healing.
Designed to NEVER raise — a watchdog that crashes is useless.
"""

from __future__ import annotations

import argparse
import subprocess
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LOG = REPO / "logs" / "docker-watchdog.log"
# Docker Desktop is installed per-user on this host; the Program Files path
# does not exist, so Popen silently failed and "healing" only worked when DD
# restarted on its own. Try per-user first, then machine-wide.
DOCKER_DESKTOP_CANDIDATES = [
    Path(r"C:\Users\tbaltzakis\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe"),
    Path(r"C:\Program Files\Docker\Docker\Docker Desktop.exe"),
]
LOG_CAP = 1_000_000


def log(line: str) -> None:
    try:
        if LOG.exists() and LOG.stat().st_size > LOG_CAP:
            LOG.write_text(
                LOG.read_text(encoding="utf-8", errors="replace")[-LOG_CAP // 2 :],
                encoding="utf-8",
            )
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"[{stamp}] {line}\n")
    except OSError:
        pass


def engine_up() -> bool:
    try:
        proc = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=25,
        )
        return proc.returncode == 0 and bool(proc.stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        return False


def start_desktop() -> None:
    for exe in DOCKER_DESKTOP_CANDIDATES:
        if exe.exists():
            try:
                subprocess.Popen([str(exe)])
                log(f"Docker Desktop started ({exe})")
                return
            except OSError as exc:
                log(f"Docker Desktop start failed ({exe}): {exc}")
    log("Docker Desktop start failed: no known install path found")


def compose_up() -> bool:
    try:
        proc = subprocess.run(
            ["docker", "compose", "up", "-d"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=180,
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def heal() -> bool:
    log("engine down — healing")
    start_desktop()
    deadline = time.monotonic() + 360
    while time.monotonic() < deadline:
        time.sleep(15)
        if engine_up():
            log("engine recovered")
            break
    else:
        log("engine STILL down after 6 min — giving up until the next run")
        return False
    if compose_up():
        log("dashboard compose up OK")
    else:
        log("dashboard compose up failed (will retry next run)")
    return True


def container_running() -> bool:
    try:
        proc = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                "name=galaxy-s22-toolkit-dashboard-1",
                "--filter",
                "status=running",
                "-q",
            ],
            capture_output=True,
            text=True,
            timeout=25,
        )
        return proc.returncode == 0 and bool(proc.stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check-only", action="store_true", help="report, do not heal")
    args = parser.parse_args(argv)
    try:
        if not engine_up():
            if args.check_only:
                log("engine down (--check-only)")
                return 1
            if not heal():
                return 1
        if not container_running():
            log("dashboard container not running — composing up")
            if not compose_up():
                log("dashboard compose up failed (will retry next run)")
                return 1
        return 0
    except Exception as exc:  # noqa: BLE001 - the watchdog must never crash
        log(f"watchdog error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
