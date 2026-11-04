"""Unit tests for battery module."""

from __future__ import annotations

from phone.battery import BatteryModule
from phone.models import BatteryHealth, BatteryStatus


class TestBatteryModule:
    """Tests for BatteryModule."""

    def test_get_battery_info(self, mock_adb_client):
        """Test parsing battery info from dumpsys output."""
        module = BatteryModule(mock_adb_client)
        battery = module.get_battery_info()

        assert battery.level == 78
        assert battery.current_ma == 76
        assert battery.charge_counter_uah == 3200
        assert battery.health == BatteryHealth.GOOD
        assert battery.status == BatteryStatus.CHARGING
        assert battery.temperature_c == 29.5
        assert battery.voltage_mv == 4123
        assert battery.technology == "Li-ion"
        assert battery.plugged_type == "USB"
        assert battery.present is True
        assert battery.scale == 100

    def test_is_charging(self, mock_adb_client):
        """Test is_charging property."""
        module = BatteryModule(mock_adb_client)
        assert module.is_charging() is True

    def test_get_temperature_c(self, mock_adb_client):
        """Get temperature in Celsius."""
        module = BatteryModule(mock_adb_client)
        temp = module.get_temperature_c()
        assert temp == 29.5

    def test_get_temperature_f(self, mock_adb_client):
        """Get temperature in Fahrenheit."""
        module = BatteryModule(mock_adb_client)
        temp_f = module.get_temperature_f()
        expected_f = 29.5 * 9 / 5 + 32
        assert temp_f == expected_f

    def test_get_level(self, mock_adb_client):
        """Get battery level."""
        module = BatteryModule(mock_adb_client)
        level = module.get_level()
        assert level == 78

    def test_get_health(self, mock_adb_client):
        """Get battery health."""
        module = BatteryModule(mock_adb_client)
        health = module.get_health()
        assert health == BatteryHealth.GOOD

    def test_get_charge_cycles(self, mock_adb_client):
        """Get charge cycles from batterystats."""
        module = BatteryModule(mock_adb_client)
        cycles = module.get_charge_cycles()
        assert cycles == 42  # From mock batterystats checkin

    def test_battery_different_health_states(self, mock_adb_client):
        """Test parsing different battery health states."""
        # Test OVERHEAT (3)
        mock_adb_client.execute.return_value = """Current Battery Service state:
  AC powered: false
  USB powered: false
  Wireless powered: false
  status: 3
  health: 3
  present: true
  level: 50
  scale: 100
  voltage: 4000
  temperature: 450
  technology: Li-ion
"""
        module = BatteryModule(mock_adb_client)
        battery = module.get_battery_info()
        assert battery.health == BatteryHealth.OVERHEAT

    def test_battery_different_status_states(self, mock_adb_client):
        """Test parsing different battery status states."""
        # Test FULL (5)
        mock_adb_client.execute.return_value = """Current Battery Service state:
  AC powered: true
  USB powered: false
  Wireless powered: false
  status: 5
  health: 2
  present: true
  level: 100
  scale: 100
  voltage: 4300
  temperature: 300
  technology: Li-ion
"""
        module = BatteryModule(mock_adb_client)
        battery = module.get_battery_info()
        assert battery.status == BatteryStatus.FULL
        assert battery.plugged_type == "AC"

    def test_battery_not_present(self, mock_adb_client):
        """Test battery not present."""
        mock_adb_client.execute.return_value = """Current Battery Service state:
  present: false
"""
        module = BatteryModule(mock_adb_client)
        battery = module.get_battery_info()
        assert battery.present is False
        assert battery.level == 0  # Default when not present
