"""Privileged (root) operations. All privileged execution is explicitly gated."""

from __future__ import annotations

import re

from .adb import AdbClient
from .exceptions import PhoneError
from .models import RootInfo


class RootModule:
    """Root/Magisk operations. Pre-root every call degrades gracefully.

    Safety model:
    - run_privileged() raises PhoneError unless confirm=True is passed.
    - No bootloader/Odin operations here — see rooting/RUNBOOK.md (manual only).
    """

    def __init__(self, client: AdbClient) -> None:
        self.client = client

    def is_rooted(self) -> bool:
        """True when `su` resolves on the device."""
        try:
            output = self.client.execute("shell", "which su")
            su_path = output.strip()
            if not su_path or su_path.startswith("which:"):
                return False
            self._last_su_path = su_path
            return True
        except Exception:
            return False

    def get_root_info(self) -> RootInfo:
        """Collect root/Magisk state. Never raises pre-root."""
        info = RootInfo()
        info.rooted = self.is_rooted()
        if info.rooted:
            info.su_path = getattr(self, "_last_su_path", None)

            ver = self.client.execute("shell", "su -c magisk -v 2>/dev/null")
            m = re.search(r"MAGISK_MAIN_VERSION[:=]?\s*([\w.]+)", ver)
            info.magisk_version = m.group(1) if m else (ver.strip() or None)

            deny = self.client.execute("shell", "su -c magisk --sqlite \"SELECT value FROM settings WHERE key='denylist'\" 2>/dev/null")
            info.denylist_enabled = deny.strip().endswith("1")

            modules = self.client.execute("shell", "su -c ls /data/adb/modules 2>/dev/null")
            info.modules_dir_present = "No such file" not in modules and modules.strip() != ""
        else:
            # Knox bit is readable without root
            knox = self.client.execute(
                "shell",
                "getprop ro.boot.warranty_bit; getprop ro.warranty_bit; getprop ro.boot.vbmeta.device_state",
            )
            bits = knox.strip().split()
            if "1" in bits:
                info.knox_status = "tripped"
            elif "0" in bits:
                info.knox_status = "intact"

        # Knox props are readable either way; refine if root run above skipped them
        knox = self.client.execute(
            "shell",
            "getprop ro.boot.warranty_bit; getprop ro.warranty_bit; getprop ro.boot.vbmeta.device_state",
        )
        bits = knox.strip().split()
        if "1" in bits:
            info.knox_status = "tripped"
        elif "0" in bits and info.knox_status == "unknown":
            info.knox_status = "intact"
        return info

    def run_privileged(self, command: str, confirm: bool = False, timeout: float | None = None) -> str:
        """Run `command` as root via su. Requires confirm=True.

        Raises:
            PhoneError: when confirm is not True.
            CommandFailedError: when su is unavailable or the command fails.
        """
        if not confirm:
            raise PhoneError(
                "run_privileged() requires confirm=True. Privileged execution is "
                "explicitly gated — no accidental root commands."
            )
        output = self.client.execute("shell", f"su -c '{command}'", timeout=timeout)
        return output

    def list_modules(self) -> list[dict[str, str]]:
        """List installed Magisk modules from /data/adb/modules."""
        if not self.is_rooted():
            return []
        raw = self.run_privileged("ls /data/adb/modules", confirm=True)
        modules = []
        for entry in raw.strip().split():
            if not entry:
                continue
            module_id = entry.strip("/").split("/")[-1]
            disabled = self.client.execute("shell", f"su -c test -f /data/adb/modules/{module_id}/disable && echo yes || echo no").strip()
            remove = self.client.execute("shell", f"su -c test -f /data/adb/modules/{module_id}/remove && echo yes || echo no").strip()
            modules.append({
                "id": module_id,
                "disabled": disabled == "yes",
                "pending_removal": remove == "yes",
            })
        return modules

    def set_module_state(self, module_id: str, action: str, confirm: bool = False) -> bool:
        """Enable/disable/remove a Magisk module by touching marker files.

        action: enable | disable | remove
        """
        if action not in ("enable", "disable", "remove"):
            raise PhoneError(f"Unknown module action: {action}")
        if not confirm:
            raise PhoneError(f"Module {action} requires confirm=True.")

        base = f"/data/adb/modules/{module_id}"
        if action == "enable":
            self.run_privileged(f"rm -f {base}/disable {base}/remove", confirm=True)
            return True
        marker = "disable" if action == "disable" else "remove"
        self.run_privileged(f"touch {base}/{marker}", confirm=True)
        return True
