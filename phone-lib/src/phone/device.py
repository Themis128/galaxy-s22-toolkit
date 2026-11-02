"""Device information retrieval via getprop and other system properties."""

from __future__ import annotations

import re
from typing import Any

from .adb import AdbClient
from .models import DeviceInfo


class DeviceModule:
    """Device information module for retrieving system properties."""

    def __init__(self, client: AdbClient) -> None:
        self.client = client

    def get_all_props(self) -> dict[str, str]:
        """Get all system properties as a dictionary."""
        output = self.client.execute("shell", "getprop")
        props = {}
        for line in output.strip().split("\n"):
            match = re.match(r"^\[(.+?)\]:\s*\[(.*)\]$", line.strip())
            if match:
                props[match.group(1)] = match.group(2)
        return props

    def get_prop(self, key: str) -> str | None:
        """Get a single system property."""
        output = self.client.execute("shell", "getprop", key)
        return output.strip() if output.strip() else None

    def get_device_info(self) -> DeviceInfo:
        """Get comprehensive device information."""
        props = self.get_all_props()

        def get(key: str, default: str = "") -> str:
            return props.get(key, default)

        # Parse API level safely
        try:
            api_level = int(get("ro.build.version.sdk", "0"))
        except ValueError:
            api_level = 0

        # Parse screen density
        density_str = get("ro.sf.lcd_density", "")
        try:
            screen_density = int(density_str) if density_str else None
        except ValueError:
            screen_density = None

        # Parse screen resolution
        width = None
        height = None
        display_width = get("ro.vendor.display.width", "")
        display_height = get("ro.vendor.display.height", "")
        if display_width and display_height:
            try:
                width = int(display_width)
                height = int(display_height)
            except ValueError:
                pass

        return DeviceInfo(
            serial=self.client.get_serial(),
            model=get("ro.product.model"),
            manufacturer=get("ro.product.manufacturer"),
            brand=get("ro.product.brand"),
            device=get("ro.product.device"),
            product=get("ro.product.name"),
            android_version=get("ro.build.version.release"),
            api_level=api_level,
            security_patch=get("ro.build.version.security_patch"),
            build_fingerprint=get("ro.build.fingerprint"),
            build_id=get("ro.build.id"),
            build_type=get("ro.build.type"),
            build_tags=get("ro.build.tags"),
            build_number=get("ro.build.display.id"),
            kernel_version=self._get_kernel_version(),
            bootloader=get("ro.bootloader"),
            hardware=get("ro.hardware"),
            cpu_abi=get("ro.product.cpu.abi"),
            cpu_abi2=get("ro.product.cpu.abi2"),
            screen_density=screen_density,
            screen_width=width,
            screen_height=height,
            total_memory=self._get_total_memory(),
        )

    def _get_kernel_version(self) -> str | None:
        """Get kernel version from /proc/version."""
        try:
            output = self.client.execute("shell", "cat", "/proc/version")
            match = re.search(r"Linux version (\S+)", output)
            return match.group(1) if match else None
        except Exception:
            return None

    def get_android_version(self) -> str:
        """Get Android version string."""
        return self.get_prop("ro.build.version.release") or "Unknown"

    def get_api_level(self) -> int:
        """Get Android API level."""
        try:
            return int(self.get_prop("ro.build.version.sdk") or "0")
        except ValueError:
            return 0

    def get_security_patch(self) -> str:
        """Get security patch date (YYYY-MM-DD)."""
        return self.get_prop("ro.build.version.security_patch") or "Unknown"

    def get_build_fingerprint(self) -> str:
        """Get build fingerprint."""
        return self.get_prop("ro.build.fingerprint") or "Unknown"

    def is_rooted(self) -> bool:
        """Check if device appears to be rooted."""
        # Check for su binary
        try:
            output = self.client.execute("shell", "which", "su", check=False)
            if output.strip():
                return True
        except Exception:
            pass

        # Check for common root indicators
        try:
            output = self.client.execute("shell", "ls", "/system/xbin/su", check=False)
            # Check if the output indicates the file exists (not an error message)
            if output.strip() and "No such file" not in output and "not found" not in output.lower():
                return True
        except Exception:
            pass

        return False

    def get_cpu_info(self) -> dict[str, Any]:
        """Get CPU information from /proc/cpuinfo."""
        output = self.client.execute("shell", "cat", "/proc/cpuinfo")
        cpus = []
        current_cpu = {}
        for line in output.strip().split("\n"):
            line = line.strip()
            if not line:
                if current_cpu:
                    cpus.append(current_cpu)
                    current_cpu = {}
                continue
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                # New processor entry starts a new CPU
                if key == "processor":
                    if current_cpu:
                        cpus.append(current_cpu)
                    current_cpu = {"processor": value}
                # Don't treat "Processor" (the header line) as a CPU entry
                elif key == "Processor":
                    # Store as general info, don't count as CPU
                    current_cpu[key] = value
                else:
                    current_cpu[key] = value
        if current_cpu:
            cpus.append(current_cpu)
        # Filter out non-processor entries (like the Features section at the end)
        cpus = [cpu for cpu in cpus if "processor" in cpu]
        return {
            "count": len(cpus),
            "details": cpus,
        }

    def get_memory_info(self) -> dict[str, int]:
        """Get memory info from /proc/meminfo in KB."""
        output = self.client.execute("shell", "cat", "/proc/meminfo")
        meminfo = {}
        for line in output.strip().split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip().replace(" kB", "")
                try:
                    meminfo[key] = int(value)
                except ValueError:
                    pass
        return meminfo

    def _get_total_memory(self) -> int | None:
        """Get total memory in KB from /proc/meminfo."""
        try:
            output = self.client.execute("shell", "cat", "/proc/meminfo")
            for line in output.strip().split("\n"):
                if line.startswith("MemTotal:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        return int(parts[1])
        except Exception:
            pass
        return None

    def get_wifi_ip(self) -> str | None:
        """Get device Wi-Fi IP address."""
        try:
            output = self.client.execute("shell", "ip", "-f", "inet", "addr", "show", "wlan0")
            for line in output.split("\n"):
                line = line.strip()
                if line.startswith("inet "):
                    # Format: "inet 192.168.1.100/24 brd 192.168.1.255 scope global wlan0"
                    ip = line.split()[1].split("/")[0]
                    return ip
        except Exception:
            pass
        return None

    def enable_wireless_adb(self, port: int = 5555) -> str:
        """Enable ADB over TCP/IP (wireless debugging).

        Returns the device IP address for connection.

        Raises:
            CommandFailedError: If tcpip command fails
        """
        # Enable TCP/IP mode on device
        self.client.execute("tcpip", str(port))

        # Get device IP
        ip = self.get_wifi_ip()
        if not ip:
            raise RuntimeError("Could not determine device Wi-Fi IP address")

        return ip

    def disable_wireless_adb(self) -> None:
        """Disable ADB over TCP/IP (restore USB-only mode)."""
        self.client.execute("shell", "setprop", "service.adb.tcp.port", "-1")
        self.client.execute("shell", "stop", "adbd")
        self.client.execute("shell", "start", "adbd")

    def connect_wireless(self, ip: str, port: int = 5555) -> str:
        """
        Connect to device via wireless ADB.

        This is typically called from the host machine, not the device.
        Returns connection output.
        """
        return self.client.execute("connect", f"{ip}:{port}")

    def disconnect_wireless(self, ip: str, port: int = 5555) -> str:
        """Disconnect from wireless ADB."""
        return self.client.execute("disconnect", f"{ip}:{port}")

    def get_wireless_status(self) -> dict[str, Any]:
        """Get current wireless ADB status."""
        result = {
            "tcp_port": None,
            "wifi_ip": self.get_wifi_ip(),
            "connected_devices": [],
        }

        # Check if adbd is listening on TCP port
        try:
            output = self.client.execute("shell", "getprop", "service.adb.tcp.port")
            if output.strip() and output.strip() != "-1":
                result["tcp_port"] = int(output.strip())
        except Exception:
            pass

        # Get connected devices from host perspective
        try:
            devices = self.client.list_devices()
            result["connected_devices"] = [
                {"serial": d["serial"], "state": d["state"]}
                for d in devices
            ]
        except Exception:
            pass

        return result
