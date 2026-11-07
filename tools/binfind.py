"""Locate winget-installed binaries whose Links dir is missing from stale PATHs.

winget puts command aliases in %LOCALAPPDATA%\\Microsoft\\WinGet\\Links, but a
long-lived shell (or a service) may have started before that dir was added to
PATH. This finder probes PATH first, then the Links dir, then the package dir.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def find_binary(name: str, winget_id: str | None = None) -> str | None:
    """Absolute path of ``name`` (PATH, then winget Links, then package glob)."""
    found = shutil.which(name)
    if found:
        return found
    local = Path(os.getenv("LOCALAPPDATA", "")) / "Microsoft" / "WinGet"
    links = local / "Links"
    candidate = links / f"{name}.exe"
    if candidate.exists():
        return str(candidate)
    if winget_id:
        packages = local / "Packages"
        if packages.is_dir():
            for pkg_dir in packages.glob(f"{winget_id}*"):
                for exe in pkg_dir.rglob(f"{name}.exe"):
                    return str(exe)
    return None
