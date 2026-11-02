"""Battery information from dumpsys battery and batterystats."""

from __future__ import annotations

import re
from typing import Any

from .adb import AdbClient
from .models import BatteryHealth, BatteryInfo, BatteryStatus


class BatteryModule:
    """Battery information module."""

    def __init__(self, client: AdbClient) -> None:
        self.client = client

    def get_battery_health(self) -> BatteryInfo:
        """Get battery health information (alias for get_battery_info for diagnostics compatibility)."""
        return self.get_battery_info()

    def get_battery_info(self) -> BatteryInfo:
        """Get comprehensive battery information from dumpsys battery."""
        output = self.client.execute("shell", "dumpsys", "battery")
        return self._parse_battery_dumpsys(output)

    def _parse_battery_dumpsys(self, output: str) -> BatteryInfo:
        """Parse dumpsys battery output."""
        data = {}
        for line in output.strip().split("\n"):
            line = line.strip()
            if ":" in line:
                key, value = line.split(":", 1)
                data[key.strip()] = value.strip()

        # Parse values with defaults
        level = int(data.get("level", "0"))
        health_str = data.get("health", "Unknown")
        status_str = data.get("status", "Unknown")
        temperature = int(data.get("temperature", "0")) / 10.0  # deciseconds to celsius
        voltage = int(data.get("voltage", "0"))  # millivolts
        technology = data.get("technology", "Unknown")
        scale = int(data.get("scale", "100"))

        # Map health
        health_map = {
            "1": BatteryHealth.UNKNOWN,
            "2": BatteryHealth.GOOD,
            "3": BatteryHealth.OVERHEAT,
            "4": BatteryHealth.DEAD,
            "5": BatteryHealth.OVER_VOLTAGE,
            "6": BatteryHealth.UNSPECIFIED_FAILURE,
            "7": BatteryHealth.COLD,
            "8": BatteryHealth.WATCHDOG_TIMER_EXPIRE,
            "9": BatteryHealth.SAFETY_TIMER_EXPIRE,
        }
        health = health_map.get(health_str, BatteryHealth.UNKNOWN)

        # Map status
        status_map = {
            "1": BatteryStatus.UNKNOWN,
            "2": BatteryStatus.CHARGING,
            "3": BatteryStatus.DISCHARGING,
            "4": BatteryStatus.NOT_CHARGING,
            "5": BatteryStatus.FULL,
        }
        status = status_map.get(status_str, BatteryStatus.UNKNOWN)

        # Determine plugged type
        plugged_type = "Unknown"
        if data.get("AC powered") == "true":
            plugged_type = "AC"
        elif data.get("USB powered") == "true":
            plugged_type = "USB"
        elif data.get("Wireless powered") == "true":
            plugged_type = "Wireless"

        # Get additional info from batterystats if available
        max_capacity = None
        current_capacity = None
        charge_cycles = None
        try:
            self._get_batterystats_extras()
        except Exception:
            pass

        return BatteryInfo(
            level=level,
            health=health,
            status=status,
            temperature_c=temperature,
            voltage_mv=voltage,
            technology=technology,
            plugged_type=plugged_type,
            max_capacity_mah=max_capacity,
            current_capacity_mah=current_capacity,
            charge_cycles=charge_cycles,
            present=data.get("present", "true").lower() == "true",
            scale=scale,
        )

    def _get_batterystats_extras(self) -> dict[str, Any]:
        """Get additional battery stats from dumpsys batterystats."""
        output = self.client.execute("shell", "dumpsys", "batterystats", "--checkin")
        stats = {}
        for line in output.strip().split("\n"):
            if line.startswith("9,"):  # Battery info line in checkin format
                parts = line.split(",")
                if len(parts) > 5:
                    try:
                        stats["charge_cycles"] = int(parts[5]) if parts[5] else None
                    except (ValueError, IndexError):
                        pass
        return stats

    def get_charge_cycles(self) -> int | None:
        """Get battery charge cycles from batterystats."""
        try:
            stats = self._get_batterystats_extras()
            return stats.get("charge_cycles")
        except Exception:
            return None

    def get_battery_history(self, hours: int = 24) -> list[dict[str, Any]]:
        """Get battery history for the last N hours."""
        self.client.execute("shell", "dumpsys", "batterystats", "--history")
        # Parse history - simplified for now
        return []

    def is_charging(self) -> bool:
        """Check if battery is currently charging."""
        info = self.get_battery_info()
        return info.is_charging

    def get_temperature_c(self) -> float:
        """Get current battery temperature in Celsius."""
        info = self.get_battery_info()
        return info.temperature_c

    def get_temperature_f(self) -> float:
        """Get current battery temperature in Fahrenheit."""
        info = self.get_battery_info()
        return info.temperature_f

    def get_level(self) -> int:
        """Get current battery level (0-100)."""
        info = self.get_battery_info()
        return info.level

    def get_health(self) -> BatteryHealth:
        """Get battery health status."""
        info = self.get_battery_info()
        return info.health

    def estimate_time_remaining(self) -> tuple[int | None, int | None]:
        """
        Estimate time to full (if charging) or time to empty (if discharging).
        Returns (hours, minutes) or (None, None) if unavailable.
        """
        try:
            output = self.client.execute("shell", "dumpsys", "batterystats")
            # Look for time estimates in batterystats
            for line in output.split("\n"):
                if "timeToFull" in line or "timeToEmpty" in line:
                    match = re.search(r"(\d+)\s*(min|h)", line)
                    if match:
                        value = int(match.group(1))
                        unit = match.group(2)
                        if unit == "h":
                            return (value, 0)
                        else:
                            return (0, value)
        except Exception:
            pass
        return (None, None)
