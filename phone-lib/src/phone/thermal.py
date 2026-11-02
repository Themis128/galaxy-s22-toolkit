"""Thermal zone and throttling information."""

from __future__ import annotations

from typing import Any

from .adb import AdbClient
from .models import ThermalInfo, ThermalStatus, ThermalZone


class ThermalModule:
    """Thermal information module."""

    def __init__(self, client: AdbClient) -> None:
        self.client = client

    def get_thermal_info(self) -> ThermalInfo:
        """Get comprehensive thermal information."""
        zones = self.get_thermal_zones()
        cpu_throttled, gpu_throttled = self._check_throttling()
        status = self._determine_status(zones, cpu_throttled, gpu_throttled)

        return ThermalInfo(
            zones=zones,
            cpu_throttled=cpu_throttled,
            gpu_throttled=gpu_throttled,
            status=status,
        )

    def get_thermal_zones(self) -> list[ThermalZone]:
        """Get all thermal zones and their temperatures."""
        zones = []
        try:
            # Find thermal zone directories
            output = self.client.execute("shell", "ls", "/sys/class/thermal/")
            zone_dirs = [d for d in output.strip().split("\n") if d.startswith("thermal_zone")]

            for zone_dir in zone_dirs:
                zone = self._read_thermal_zone(zone_dir)
                if zone:
                    zones.append(zone)
        except Exception:
            pass

        # Also check for Samsung-specific thermal zones
        try:
            output = self.client.execute("shell", "ls", "/sys/devices/virtual/thermal/")
            for zone_dir in output.strip().split("\n"):
                if zone_dir.startswith("thermal_zone"):
                    zone = self._read_thermal_zone(f"virtual/thermal/{zone_dir}")
                    if zone:
                        zones.append(zone)
        except Exception:
            pass

        return zones

    def _read_thermal_zone(self, zone_path: str) -> ThermalZone | None:
        """Read a single thermal zone's temperature and type."""
        try:
            # Read temperature (in millicelsius)
            temp_output = self.client.execute("shell", "cat", f"/sys/class/thermal/{zone_path}/temp")
            temp_mc = int(temp_output.strip())
            temp_c = temp_mc / 1000.0

            # Read type
            type_output = self.client.execute("shell", "cat", f"/sys/class/thermal/{zone_path}/type")
            zone_type = type_output.strip()

            return ThermalZone(
                name=zone_path,
                temp_c=temp_c,
                type=zone_type,
            )
        except Exception:
            return None

    def _check_throttling(self) -> tuple[bool, bool]:
        """Check if CPU/GPU are throttled."""
        cpu_throttled = False
        gpu_throttled = False

        try:
            # Check CPU throttling via thermal zones
            for zone in self.get_thermal_zones():
                if zone.type and "cpu" in zone.type.lower():
                    # Throttling typically starts around 80-85°C
                    if zone.temp_c >= 80:
                        cpu_throttled = True

                if zone.type and "gpu" in zone.type.lower():
                    if zone.temp_c >= 80:
                        gpu_throttled = True

            # Also check for throttling in dumpsys
            output = self.client.execute("shell", "dumpsys", "thermalservice", check=False)
            output_lower = output.lower()
            # Check for actual throttling (not "throttling: none")
            if "throttling" in output_lower and "none" not in output_lower:
                if "cpu" in output_lower:
                    cpu_throttled = True
                if "gpu" in output_lower:
                    gpu_throttled = True

        except Exception:
            pass

        return cpu_throttled, gpu_throttled

    def _determine_status(
        self, zones: list[ThermalZone], cpu_throttled: bool, gpu_throttled: bool
    ) -> ThermalStatus:
        """Determine overall thermal status."""
        if not zones:
            return ThermalStatus.NORMAL

        max_temp = max(z.temp_c for z in zones)

        if cpu_throttled or gpu_throttled:
            if max_temp >= 95:
                return ThermalStatus.CRITICAL
            if max_temp >= 85:
                return ThermalStatus.SEVERE
            return ThermalStatus.THROTTLED

        if max_temp >= 85:
            return ThermalStatus.SEVERE
        if max_temp >= 75:
            return ThermalStatus.THROTTLED
        if max_temp >= 65:
            return ThermalStatus.NORMAL  # Warm but normal
        return ThermalStatus.NORMAL

    def get_cpu_temperature(self) -> float | None:
        """Get CPU temperature in Celsius."""
        for zone in self.get_thermal_zones():
            if zone.type and "cpu" in zone.type.lower():
                return zone.temp_c
        return None

    def get_gpu_temperature(self) -> float | None:
        """Get GPU temperature in Celsius."""
        for zone in self.get_thermal_zones():
            if zone.type and "gpu" in zone.type.lower():
                return zone.temp_c
        return None

    def get_battery_temperature(self) -> float | None:
        """Get battery temperature in Celsius."""
        for zone in self.get_thermal_zones():
            if zone.type and "battery" in zone.type.lower():
                return zone.temp_c
        return None

    def get_skin_temperature(self) -> float | None:
        """Get skin/surface temperature in Celsius."""
        for zone in self.get_thermal_zones():
            if zone.type and ("skin" in zone.type.lower() or "surface" in zone.type.lower()):
                return zone.temp_c
        return None

    def is_throttling(self) -> bool:
        """Check if any thermal throttling is active."""
        info = self.get_thermal_info()
        return info.cpu_throttled or info.gpu_throttled or info.status != ThermalStatus.NORMAL

    def get_throttling_status(self) -> bool:
        """Get throttling status (alias for diagnostics compatibility)."""
        return self.is_throttling()

    def get_throttling_details(self) -> dict[str, Any]:
        """Get detailed throttling information."""
        info = self.get_thermal_info()
        return {
            "cpu_throttled": info.cpu_throttled,
            "gpu_throttled": info.gpu_throttled,
            "status": info.status.value,
            "max_temp_c": max((z.temp_c for z in info.zones), default=0),
            "zones": [
                {"name": z.name, "temp_c": z.temp_c, "type": z.type}
                for z in info.zones
            ],
        }

    def monitor_thermal(
        self,
        callback: callable,
        interval: float = 5.0,
        threshold_c: float = 70.0,
    ) -> None:
        """Monitor thermal zones and call callback when threshold exceeded."""
        import threading
        import time

        def monitor():
            while True:
                info = self.get_thermal_info()
                max_temp = max((z.temp_c for z in info.zones), default=0)
                if max_temp >= threshold_c or info.cpu_throttled or info.gpu_throttled:
                    callback(info)
                time.sleep(interval)

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
