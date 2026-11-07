"""iOS device support via libimobiledevice — the iTunes-free pillar.

Wraps the libimobiledevice CLI suite (idevice_id/ideviceinfo/idevicebackup2/
idevicescreenshot/ideviceinstaller) behind a typed client, mirroring the
AdbClient module pattern. Windows needs the Apple Mobile Device driver (or
the usbmuxd service); missing binaries degrade to honest PhoneErrors.

No jailbreak, no activation/lock bypass — backup, inspect, restore only.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .exceptions import PhoneError


@dataclass
class IMobileInfo:
    """Identity subset parsed from `ideviceinfo`."""

    udid: str = ""
    name: str = "unknown"
    model: str = "unknown"
    ios_version: str = "unknown"
    product_type: str = "unknown"
    raw: dict[str, str] = field(default_factory=dict)


def _run(cmd: list[str], timeout: float = 30.0) -> str:
    exe = shutil.which(cmd[0])
    if exe is None:
        raise PhoneError(
            f"{cmd[0]} not installed — install libimobiledevice (https://libimobiledevice.org)"
        )
    try:
        proc = subprocess.run([exe, *cmd[1:]], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PhoneError(f"{cmd[0]} failed: {exc}") from exc
    if proc.returncode != 0:
        stderr = (proc.stderr or proc.stdout).strip()
        raise PhoneError(f"{cmd[0]} failed: {stderr[:200] or f'exit {proc.returncode}'}")
    return proc.stdout


def list_udids() -> list[str]:
    """UDIDs of attached iOS devices (empty when none / drivers missing)."""
    out = _run(["idevice_id", "-l"])
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def parse_ideviceinfo(out: str) -> dict[str, str]:
    """Parse `ideviceinfo` key: value output (pure; unit-tested)."""
    props: dict[str, str] = {}
    for line in out.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        if key:
            props[key] = value.strip()
    return props


class IMobileClient:
    """One attached iOS device (UDID auto-selected when unambiguous)."""

    def __init__(self, udid: str | None = None) -> None:
        self.udid = udid or self._resolve_udid()

    def _resolve_udid(self) -> str:
        udids = list_udids()
        if not udids:
            raise PhoneError(
                "No iOS device attached (or the Apple Mobile Device driver / "
                "usbmuxd service is missing)"
            )
        if len(udids) > 1:
            raise PhoneError(
                f"Multiple iOS devices attached ({len(udids)}) — pass an explicit UDID"
            )
        return udids[0]

    def _u(self, cmd: list[str], timeout: float = 30.0) -> str:
        """Run a libimobiledevice tool scoped to this device UDID."""
        return _run([cmd[0], "-u", self.udid, *cmd[1:]], timeout)

    def get_info(self) -> IMobileInfo:
        out = self._u(["ideviceinfo"], timeout=45.0)
        props = parse_ideviceinfo(out)
        return IMobileInfo(
            udid=self.udid,
            name=props.get("DeviceName", "unknown"),
            model=props.get("ProductType", "unknown"),
            ios_version=props.get("ProductVersion", "unknown"),
            product_type=props.get("ProductType", "unknown"),
            raw=props,
        )

    def backup(self, dest_dir: Path, full: bool = False) -> str:
        """Run idevicebackup2 (long; runs synchronously — hours for a first full)."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        args = ["idevicebackup2", "backup"] + (["--full"] if full else []) + [str(dest_dir)]
        return _run(args, timeout=3600.0 * 12)

    def restore(self, backup_dir: Path, system: bool = True, settings: bool = True) -> str:
        args = ["idevicebackup2", "restore"]
        if system:
            args.append("--system")
        if settings:
            args.append("--settings")
        args.append(str(backup_dir))
        return _run(args, timeout=3600.0 * 12)

    def screenshot(self, out_png: Path) -> Path:
        out_png.parent.mkdir(parents=True, exist_ok=True)
        self._u(["idevicescreenshot", str(out_png)], timeout=60.0)
        return out_png

    def list_apps(self) -> list[str]:
        out = self._u(["ideviceinstaller", "-l"], timeout=120.0)
        return [
            ln.strip() for ln in out.splitlines() if ln.strip() and not ln.startswith("CFBundle")
        ]
