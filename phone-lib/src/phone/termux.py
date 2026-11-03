"""Termux API integration for Android device management.

This module provides integration with Termux environment on Android devices,
enabling direct device API access, environment configuration, and automation.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Any


class TermuxApiCommand(Enum):
    """Termux API command names."""

    BATTERY_STATUS = "termux-battery-status"
    BATTERY_LEVEL = "termux-battery-level"
    BLUETOOTH_STATUS = "termux-bluetooth-status"
    CPU_INFO = "termux-cpu-info"
    ENV = "termux-env"
    FINGERPRINT = "termux-fingerprint"
    GLIDE_CONTEXT = "termux-glide-context"
    INET_FINGERPRINT = "termux-inet-fingerprint"
    LOCATION = "termux-location"
    MEMINFO = "termux-meminfo"
    NETWORK_STATUS = "termux-network-profile"
    PHONE_INFO = "termux-telephony-deviceinfo"
    PHONE_STATUS = "termux-telephony-deviceinfo"
    SMS = "termux-sms-list"
    STORAGE = "termux-storagedirs"
    USB_HOST = "termux-usb"
    WIFIINFO = "termux-wifi-info"
    WIFI_RSSI = "termux-wifi-signalinfo"
    WM_INFO = "termux-wm-info"


@dataclass(slots=True)
class TermuxBattery:
    """Battery status from Termux API."""

    level: int
    health: str
    present: bool
    status: str
    voltage: int | None = None
    temperature: int | None = None


@dataclass(slots=True)
class TermuxWifiInfo:
    """WiFi information from Termux API."""

    ssid: str | None
    bssid: str | None
    capabilities: list[str] | None
    frequency: int | None
    rssi: int | None = None


@dataclass(slots=True)
class TermuxCpuInfo:
    """CPU information from Termux API."""

    cores: int
    model: str
    frequency: int


class TermuxClient:
    """Client for interacting with Termux environment on Android."""

    TERMUX_PACKAGE = "com.termux"

    def __init__(self, check_available: bool = True) -> None:
        """
        Initialize Termux client.

        Args:
            check_available: If True, verify Termux API is installed
        """
        self._available = self._check_termux_available() if check_available else True

    def _check_termux_available(self) -> bool:
        """Check if Termux API commands are available."""
        try:
            result = subprocess.run(
                ["which", TermuxApiCommand.BATTERY_STATUS.value],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    @property
    def is_available(self) -> bool:
        """Check if Termux API is available."""
        return self._available

    def _run_command(self, command: str, *args: str) -> dict[str, Any]:
        """
        Run a Termux API command and return parsed JSON.

        Raises:
            RuntimeError: If Termux API command fails
            json.JSONDecodeError: If output is not valid JSON
        """
        if not self._available:
            raise RuntimeError(
                "Termux API is not available. "
                "Install Termux and Termux:API from F-Droid or Play Store."
            )

        try:
            result = subprocess.run(
                [command, *args],
                capture_output=True,
                text=True,
                check=True,
            )
            return json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Termux API command failed: {e.stderr}") from e
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON output: {e}") from e

    def get_battery_status(self) -> TermuxBattery:
        """Get battery status from device."""
        data = self._run_command(TermuxApiCommand.BATTERY_STATUS.value)
        return TermuxBattery(
            level=data.get("level", 0),
            health=data.get("health", "unknown"),
            present=data.get("present", False),
            status=data.get("status", "unknown"),
            voltage=data.get("voltage"),
            temperature=data.get("temperature"),
        )

    def get_battery_level(self) -> int:
        """Get current battery level percentage."""
        data = self._run_command(TermuxApiCommand.BATTERY_LEVEL.value)
        return data.get("level", 0)

    def get_wifi_info(self) -> TermuxWifiInfo:
        """Get current WiFi connection info."""
        try:
            data = self._run_command(TermuxApiCommand.WIFIINFO.value)
            return TermuxWifiInfo(
                ssid=data.get("ssid"),
                bssid=data.get("bssid"),
                capabilities=data.get("capabilities", "").split(","),
                frequency=data.get("frequency"),
            )
        except RuntimeError:
            # WiFi may be disconnected
            return TermuxWifiInfo(ssid=None, bssid=None, capabilities=None, frequency=None)

    def get_wifi_signal(self) -> int | None:
        """Get WiFi RSSI signal strength in dBm."""
        try:
            data = self._run_command(TermuxApiCommand.WIFI_RSSI.value)
            return data.get("rssi")
        except RuntimeError:
            return None

    def get_cpu_info(self) -> TermuxCpuInfo:
        """Get CPU information."""
        data = self._run_command(TermuxApiCommand.CPU_INFO.value)
        return TermuxCpuInfo(
            cores=len(data.get("cpu", {})),
            model=data.get("cpu", {}).get("0", {}).get("model", "unknown"),
            frequency=data.get("cpu", {}).get("0", {}).get("frequency", 0),
        )

    def get_memory_info(self) -> dict[str, int]:
        """Get memory information from Termux."""
        data = self._run_command(TermuxApiCommand.MEMINFO.value)
        return {
            "total": data.get("total"),
            "free": data.get("free"),
            "available": data.get("available"),
            "buffers": data.get("buffers"),
            "cached": data.get("cached"),
        }

    def get_location(self) -> dict[str, float] | None:
        """Get device location (requires location permission)."""
        try:
            data = self._run_command(TermuxApiCommand.LOCATION.value)
            if data.get("from") != "gps":
                return None
            return {
                "latitude": data.get("latitude"),
                "longitude": data.get("longitude"),
            }
        except RuntimeError:
            return None

    def get_telephony_info(self) -> dict[str, Any]:
        """Get telephony/device info."""
        return self._run_command(TermuxApiCommand.PHONE_INFO.value)

    def list_sms(self, count: int = 10) -> list[dict[str, Any]]:
        """List recent SMS messages."""
        data = self._run_command(TermuxApiCommand.SMS.value, f"{count}")
        return data if isinstance(data, list) else []

    def get_storage_dirs(self) -> list[str]:
        """Get available storage directories."""
        data = self._run_command(TermuxApiCommand.STORAGE.value)
        return data if isinstance(data, list) else []

    def broadcast(self, action: str) -> None:
        """Send broadcast intent to device."""
        # This is a helper for sending broadcasts via termux-api
        subprocess.run(
            ["termux-toast", f"Broadcast: {action}"],
            capture_output=True,
        )

    @staticmethod
    def setup_storage() -> bool:
        """
        Request storage permission (Termux special).

        This must be called from within Termux after initial install.
        The user will be prompted to grant storage access.
        """
        try:
            # This triggers the storage permission request
            result = subprocess.run(
                ["termux-setup-storage"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    @staticmethod
    def create_boot_script(script_path: str, content: str) -> str:
        """
        Create a boot script for Termux.

        Boot scripts run automatically at device boot and live in
        ~/.termux/boot/. ``script_path`` is confined inside that directory:
        ``..`` segments resolving outside are rejected with PathEscapeError.
        """
        from .paths import confined_path

        boot_dir = os.path.expanduser("~/.termux/boot")
        os.makedirs(boot_dir, exist_ok=True)

        full_path = confined_path(boot_dir, os.path.join(boot_dir, script_path))
        with open(full_path, "w") as f:
            f.write(content)

        # Make executable
        os.chmod(full_path, 0o755)

        return str(full_path)

class TermuxBootManager:
    """Manager for Termux boot scripts."""

    BOOT_DIR = os.path.expanduser("~/.termux/boot")

    @classmethod
    def list_scripts(cls) -> list[str]:
        """List all boot scripts."""
        if not os.path.exists(cls.BOOT_DIR):
            return []
        return [f for f in os.listdir(cls.BOOT_DIR) if os.access(os.path.join(cls.BOOT_DIR, f), os.X_OK)]

    @classmethod
    def remove_script(cls, name: str) -> bool:
        """Remove a boot script."""
        path = os.path.join(cls.BOOT_DIR, name)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    @classmethod
    def enable_boot(cls) -> None:
        """Enable Termux boot (creates the boot directory if needed)."""
        os.makedirs(cls.BOOT_DIR, exist_ok=True)


# Convenience functions for direct usage
def get_battery() -> int:
    """Get battery level percentage (convenience function)."""
    try:
        result = subprocess.run(
            [TermuxApiCommand.BATTERY_LEVEL.value],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)
        return data.get("level", 0)
    except Exception:
        return 0


def get_wifi_ssid() -> str | None:
    """Get current WiFi SSID (convenience function)."""
    try:
        result = subprocess.run(
            [TermuxApiCommand.WIFIINFO.value],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)
        return data.get("ssid")
    except Exception:
        return None


def get_ip_address() -> str | None:
    """Get device IP address via ip command."""
    try:
        result = subprocess.run(
            ["ip", "-f", "inet", "addr", "show", "wlan0"],
            capture_output=True,
            text=True,
            check=True,
        )
        for line in result.stdout.split("\n"):
            if line.strip().startswith("inet "):
                return line.split()[1].split("/")[0]
    except Exception:
        pass
    return None
