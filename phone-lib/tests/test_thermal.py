"""Unit tests for thermal module."""

from __future__ import annotations

import pytest

from phone.thermal import ThermalModule
from phone.models import ThermalInfo, ThermalStatus, ThermalZone


class TestThermalModule:
    """Tests for ThermalModule."""

    def test_get_thermal_info(self, mock_adb_client):
        """Test getting thermal info."""
        module = ThermalModule(mock_adb_client)
        thermal = module.get_thermal_info()
        
        assert isinstance(thermal, ThermalInfo)
        assert len(thermal.zones) == 5
        assert thermal.status == ThermalStatus.NORMAL
        assert thermal.cpu_throttled is False
        assert thermal.gpu_throttled is False

    def test_get_thermal_zones(self, mock_adb_client):
        """Test getting thermal zones from sysfs."""
        module = ThermalModule(mock_adb_client)
        zones = module.get_thermal_zones()
        
        assert len(zones) == 5
        assert all(isinstance(zone, ThermalZone) for zone in zones)
        
        # Check specific zones
        cpu0 = next((z for z in zones if z.name == "thermal_zone0"), None)
        assert cpu0 is not None
        assert cpu0.temp_c == 35.0  # 35000 millicelsius
        
        battery = next((z for z in zones if z.name == "thermal_zone3"), None)
        assert battery is not None
        assert battery.temp_c == 45.0  # 45000 millicelsius

    def test_thermal_status_critical(self, mock_adb_client):
        """Test thermal status when critical temperature reached."""
        # Override thermal zone 3 to be critical (>50C)
        mock_adb_client.execute.side_effect = lambda *args, **kwargs: {
            ("shell", "ls", "/sys/class/thermal/"): "thermal_zone0\nthermal_zone1\nthermal_zone2\nthermal_zone3\nthermal_zone4\n",
            ("shell", "ls", "/sys/devices/virtual/thermal/"): "",
            ("shell", "cat", "/sys/class/thermal/thermal_zone0/temp"): "35000\n",
            ("shell", "cat", "/sys/class/thermal/thermal_zone1/temp"): "36000\n",
            ("shell", "cat", "/sys/class/thermal/thermal_zone2/temp"): "34000\n",
            ("shell", "cat", "/sys/class/thermal/thermal_zone3/temp"): "55000\n",  # 55C
            ("shell", "cat", "/sys/class/thermal/thermal_zone4/temp"): "42000\n",
            ("shell", "cat", "/sys/class/thermal/thermal_zone0/type"): "cpu\n",
            ("shell", "cat", "/sys/class/thermal/thermal_zone1/type"): "cpu\n",
            ("shell", "cat", "/sys/class/thermal/thermal_zone2/type"): "gpu\n",
            ("shell", "cat", "/sys/class/thermal/thermal_zone3/type"): "battery\n",
            ("shell", "cat", "/sys/class/thermal/thermal_zone4/type"): "skin\n",
            ("shell", "dumpsys", "thermalservice"): """Thermal Service:
Thermal zones:
  cpu0-thermal: temp=35000 type=cpu
  cpu1-thermal: temp=36000 type=cpu
  gpu-thermal: temp=34000 type=gpu
  battery-thermal: temp=55000 type=battery
  skin-thermal: temp=42000 type=skin
Throttling: throttled
""",
        }.get(args, "")
        
        module = ThermalModule(mock_adb_client)
        thermal = module.get_thermal_info()
        
        # At 55°C with throttling, status should be THROTTLED (max < 85°C)
        assert thermal.status == ThermalStatus.THROTTLED
        assert thermal.cpu_throttled is True
        assert thermal.gpu_throttled is True
        assert any(z.temp_c > 50 for z in thermal.zones)

    def test_cpu_throttling_detection(self, mock_adb_client):
        """Test CPU throttling detection."""
        mock_adb_client.execute.return_value = """Thermal Service:
Thermal zones:
  cpu0-thermal: temp=35000 type=cpu
Throttling: throttled
"""
        module = ThermalModule(mock_adb_client)
        thermal = module.get_thermal_info()
        
        assert thermal.cpu_throttled is True