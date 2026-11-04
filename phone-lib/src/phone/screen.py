"""Screen capture, recording, and UI dump."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .adb import AdbClient


class ScreenModule:
    """Screen management module."""

    def __init__(self, client: AdbClient) -> None:
        self.client = client
        self._recording_path: str | None = None

    def screenshot(self, remote_path: str = "/sdcard/screenshot.png") -> str:
        """Take screenshot and return remote path."""
        self.client.execute("shell", "screencap", "-p", remote_path)
        return remote_path

    def screenshot_pull(
        self,
        local_path: str = ".",
        remote_path: str = "/sdcard/screenshot.png",
        filename: str | None = None,
    ) -> str:
        """Take screenshot and pull to local."""
        self.screenshot(remote_path)

        if filename is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"

        local_file = Path(local_path) / filename
        self.client.pull(remote_path, str(local_file))
        self.client.execute("shell", "rm", remote_path)
        return str(local_file)

    def start_screenrecord(
        self,
        remote_path: str = "/sdcard/record.mp4",
        time_limit: int = 180,
        bit_rate: int = 4000000,
        size: str | None = None,
    ) -> str:
        """Start screen recording (returns immediately)."""
        args = [
            "shell",
            "screenrecord",
            f"--time-limit={time_limit}",
            f"--bit-rate={bit_rate}",
        ]
        if size:
            args.append(f"--size={size}")

        args.append(remote_path)
        self._recording_path = remote_path
        self.client.execute(*args)
        return remote_path

    def stop_screenrecord(self) -> str | None:
        """Stop screen recording by sending Ctrl+C equivalent."""
        # screenrecord stops on its own after time_limit or when process is killed
        # We can't easily stop it early without killing the shell process
        return self._recording_path

    def pull_recording(
        self,
        remote_path: str | None = None,
        local_path: str = ".",
        filename: str | None = None,
    ) -> str:
        """Pull screen recording and clean up remote."""
        remote = remote_path or self._recording_path
        if not remote:
            raise ValueError("No recording path specified")

        if filename is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"record_{timestamp}.mp4"

        local_file = Path(local_path) / filename
        self.client.pull(remote, str(local_file))
        self.client.execute("shell", "rm", remote)
        self._recording_path = None
        return str(local_file)

    def record_and_pull(
        self,
        local_path: str = ".",
        filename: str | None = None,
        time_limit: int = 180,
        bit_rate: int = 4000000,
        size: str | None = None,
    ) -> str:
        """Record screen for time_limit and pull result."""
        remote = f"/sdcard/record_{time.strftime('%Y%m%d_%H%M%S')}.mp4"
        self.start_screenrecord(remote, time_limit, bit_rate, size)

        # Wait for recording to complete
        time.sleep(time_limit + 2)

        return self.pull_recording(remote, local_path, filename)

    def get_ui_dump(self, compressed: bool = False) -> str:
        """Get UI hierarchy dump (uiautomator dump)."""
        remote = "/sdcard/ui_dump.xml"
        args = ["shell", "uiautomator", "dump"]
        if compressed:
            args.append("--compressed")
        args.append(remote)

        self.client.execute(*args)
        output = self.client.execute("shell", "cat", remote)
        self.client.execute("shell", "rm", remote)
        return output

    def get_ui_dump_pull(self, local_path: str = ".") -> str:
        """Get UI dump and save to local file."""
        remote = "/sdcard/ui_dump.xml"
        self.client.execute("shell", "uiautomator", "dump", remote)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        local_file = Path(local_path) / f"ui_dump_{timestamp}.xml"
        self.client.pull(remote, str(local_file))
        self.client.execute("shell", "rm", remote)
        return str(local_file)

    def tap(self, x: int, y: int) -> str:
        """Tap screen coordinates."""
        return self.client.tap(x, y)

    def swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration: int = 300,
    ) -> str:
        """Swipe between coordinates."""
        return self.client.swipe(x1, y1, x2, y2, duration)

    def text(self, text: str) -> str:
        """Type text."""
        return self.client.text(text)

    def keyevent(self, keycode: str | int) -> str:
        """Send key event."""
        return self.client.keyevent(keycode)

    def press_back(self) -> str:
        """Press back button."""
        return self.keyevent("KEYCODE_BACK")

    def press_home(self) -> str:
        """Press home button."""
        return self.keyevent("KEYCODE_HOME")

    def press_recent(self) -> str:
        """Press recent apps button."""
        return self.keyevent("KEYCODE_APP_SWITCH")

    def press_power(self) -> str:
        """Press power button."""
        return self.keyevent("KEYCODE_POWER")

    def press_volume_up(self) -> str:
        """Press volume up."""
        return self.keyevent("KEYCODE_VOLUME_UP")

    def press_volume_down(self) -> str:
        """Press volume down."""
        return self.keyevent("KEYCODE_VOLUME_DOWN")

    def get_screen_size(self) -> tuple[int, int] | None:
        """Get screen resolution (width, height)."""
        try:
            output = self.client.execute("shell", "wm", "size")
            # Output: Physical size: 1080x2340
            match = output.strip().split()[-1]
            if "x" in match:
                width, height = map(int, match.split("x"))
                return (width, height)
        except Exception:
            pass
        return None

    def get_screen_density(self) -> int | None:
        """Get screen density (DPI)."""
        try:
            output = self.client.execute("shell", "wm", "density")
            # Output: Physical density: 420
            match = output.strip().split()[-1]
            return int(match)
        except Exception:
            pass
        return None

    def set_screen_density(self, density: int) -> bool:
        """Set screen density (requires reboot to persist)."""
        try:
            self.client.execute("shell", "wm", "density", str(density))
            return True
        except Exception:
            return False

    def reset_screen_density(self) -> bool:
        """Reset screen density to default."""
        try:
            self.client.execute("shell", "wm", "density", "reset")
            return True
        except Exception:
            return False

    def get_display_info(self) -> dict[str, Any]:
        """Get comprehensive display information."""
        info: dict[str, Any] = {}
        info["size"] = self.get_screen_size()
        info["density"] = self.get_screen_density()

        # Get display metrics
        try:
            output = self.client.execute("shell", "dumpsys", "display")
            for line in output.split("\n"):
                line = line.strip()
                if "mDisplayWidth" in line:
                    info["width"] = int(line.split("=")[1].strip())
                elif "mDisplayHeight" in line:
                    info["height"] = int(line.split("=")[1].strip())
                elif "mRefreshRate" in line:
                    info["refresh_rate"] = float(line.split("=")[1].strip())
        except Exception:
            pass

        return info

    def set_orientation(self, orientation: int) -> bool:
        """Set screen orientation (0=default, 1=landscape, 2=portrait, 3=reverse landscape, 4=reverse portrait)."""
        try:
            self.client.execute("shell", "settings", "put", "system", "user_rotation", str(orientation))
            return True
        except Exception:
            return False

    def get_orientation(self) -> int | None:
        """Get current screen orientation."""
        try:
            output = self.client.execute("shell", "settings", "get", "system", "user_rotation")
            return int(output.strip())
        except Exception:
            return None

    def take_bugreport(self, local_path: str = ".") -> str:
        """Take a bugreport and pull it."""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        remote = f"/sdcard/bugreport_{timestamp}.zip"
        local_file = Path(local_path) / f"bugreport_{timestamp}.zip"

        self.client.execute("bugreport", remote)
        self.client.pull(remote, str(local_file))
        self.client.execute("shell", "rm", remote)
        return str(local_file)
