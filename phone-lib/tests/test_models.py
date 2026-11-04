"""Unit tests for phone models."""

from __future__ import annotations

from phone.models import (
    BatteryHealth,
    BatteryInfo,
    BatteryStatus,
    DeviceInfo,
    LogEntry,
    LogLevel,
    NetworkInfo,
    StorageInfo,
    ThermalInfo,
    ThermalStatus,
    ThermalZone,
)


class TestBatteryInfo:
    """Tests for BatteryInfo model."""

    def test_battery_info_creation(self):
        battery = BatteryInfo(
            level=75,
            health=BatteryHealth.GOOD,
            status=BatteryStatus.DISCHARGING,
            temperature_c=28.5,
            voltage_mv=4100,
            technology="Li-ion",
            plugged_type="USB",
        )
        assert battery.level == 75
        assert battery.health == BatteryHealth.GOOD
        assert battery.status == BatteryStatus.DISCHARGING
        assert battery.temperature_c == 28.5

    def test_temperature_f_conversion(self):
        battery = BatteryInfo(
            level=50,
            health=BatteryHealth.GOOD,
            status=BatteryStatus.DISCHARGING,
            temperature_c=30.0,
            voltage_mv=4000,
            technology="Li-ion",
            plugged_type="Unknown",
        )
        assert battery.temperature_f == 86.0

    def test_is_charging_property(self):
        battery_charging = BatteryInfo(
            level=50,
            health=BatteryHealth.GOOD,
            status=BatteryStatus.CHARGING,
            temperature_c=30.0,
            voltage_mv=4000,
            technology="Li-ion",
            plugged_type="AC",
        )
        battery_not_charging = BatteryInfo(
            level=50,
            health=BatteryHealth.GOOD,
            status=BatteryStatus.DISCHARGING,
            temperature_c=30.0,
            voltage_mv=4000,
            technology="Li-ion",
            plugged_type="Unknown",
        )
        assert battery_charging.is_charging is True
        assert battery_not_charging.is_charging is False

    def test_is_healthy_property(self):
        battery_good = BatteryInfo(
            level=50,
            health=BatteryHealth.GOOD,
            status=BatteryStatus.DISCHARGING,
            temperature_c=30.0,
            voltage_mv=4000,
            technology="Li-ion",
            plugged_type="Unknown",
        )
        battery_bad = BatteryInfo(
            level=50,
            health=BatteryHealth.DEAD,
            status=BatteryStatus.DISCHARGING,
            temperature_c=30.0,
            voltage_mv=4000,
            technology="Li-ion",
            plugged_type="Unknown",
        )
        assert battery_good.is_healthy is True
        assert battery_bad.is_healthy is False


class TestStorageInfo:
    """Tests for StorageInfo model."""

    def test_storage_info_creation(self):
        storage = StorageInfo(
            partition="/dev/block/dm-0",
            total_bytes=5_000_000_000,
            used_bytes=3_000_000_000,
            free_bytes=2_000_000_000,
            filesystem="f2fs",
            mount_point="/data",
        )
        assert storage.partition == "/dev/block/dm-0"
        assert storage.mount_point == "/data"

    def test_gb_properties(self):
        storage = StorageInfo(
            partition="/dev/block/dm-0",
            total_bytes=5_000_000_000,
            used_bytes=3_000_000_000,
            free_bytes=2_000_000_000,
            filesystem="f2fs",
            mount_point="/data",
        )
        assert storage.total_gb == 5_000_000_000 / (1024**3)
        assert storage.used_gb == 3_000_000_000 / (1024**3)
        assert storage.free_gb == 2_000_000_000 / (1024**3)

    def test_usage_percent(self):
        storage = StorageInfo(
            partition="/dev/block/dm-0",
            total_bytes=1000,
            used_bytes=600,
            free_bytes=400,
            filesystem="f2fs",
            mount_point="/data",
        )
        assert storage.usage_percent == 60.0

    def test_usage_percent_zero_total(self):
        storage = StorageInfo(
            partition="/dev/block/dm-0",
            total_bytes=0,
            used_bytes=0,
            free_bytes=0,
            filesystem="f2fs",
            mount_point="/data",
        )
        assert storage.usage_percent == 0.0


class TestDeviceInfo:
    """Tests for DeviceInfo model."""

    def test_device_info_creation(self):
        device = DeviceInfo(
            serial="RFCTA0AEKZP",
            model="SM-S906B",
            manufacturer="samsung",
            brand="samsung",
            device="o2s",
            product="o2sxxx",
            android_version="14",
            api_level=34,
            security_patch="2024-01-01",
            build_fingerprint="samsung/o2sxxx/o2s:14/UP1A.231005.007/S906BXXU2BWK1:user/release-keys",
            build_id="UP1A.231005.007",
            build_type="user",
            build_tags="release-keys",
        )
        assert device.model == "SM-S906B"
        assert device.android_version == "14"
        assert device.api_level == 34


class TestLogEntry:
    """Tests for LogEntry model."""

    def test_parse_brief_format(self):
        line = "D/MainActivity(1234): onCreate called"
        entry = LogEntry.parse_brief(line)

        assert entry is not None
        assert entry.level == LogLevel.DEBUG
        assert entry.tag == "MainActivity"
        assert entry.pid == 1234
        assert entry.tid == 1234
        assert entry.message == "onCreate called"

    def test_parse_brief_error_level(self):
        line = "E/DatabaseHelper(5678): Failed to connect"
        entry = LogEntry.parse_brief(line)

        assert entry is not None
        assert entry.level == LogLevel.ERROR
        assert entry.tag == "DatabaseHelper"
        assert entry.pid == 5678

    def test_parse_threadtime_format(self):
        line = "11-01 14:32:45.123  1234  1235 D MainActivity: onCreate called"
        entry = LogEntry.parse_threadtime(line)

        assert entry is not None
        assert entry.level == LogLevel.DEBUG
        assert entry.tag == "MainActivity"
        assert entry.pid == 1234
        assert entry.tid == 1235
        assert entry.message == "onCreate called"
        assert entry.timestamp.month == 11
        assert entry.timestamp.day == 1
        assert entry.timestamp.hour == 14
        assert entry.timestamp.minute == 32
        assert entry.timestamp.second == 45

    def test_parse_threadtime_error(self):
        line = "11-01 14:32:45.456  5678  5678 E AndroidRuntime: FATAL EXCEPTION: main"
        entry = LogEntry.parse_threadtime(line)

        assert entry is not None
        assert entry.level == LogLevel.ERROR
        assert entry.tag == "AndroidRuntime"
        assert entry.pid == 5678
        assert entry.tid == 5678

    def test_parse_invalid_line_returns_none(self):
        entry = LogEntry.parse_brief("invalid line")
        assert entry is None

        entry = LogEntry.parse_threadtime("invalid line")
        assert entry is None


class TestNetworkInfo:
    """Tests for NetworkInfo model."""

    def test_network_info_wifi(self):
        network = NetworkInfo(
            wifi_connected=True,
            wifi_ssid="MyWiFi",
            wifi_ip="192.168.1.100",
            wifi_signal_dbm=-45,
            dns_servers=["192.168.1.1", "8.8.8.8"],
            gateway="192.168.1.1",
            internet_reachable=True,
        )
        assert network.wifi_connected is True
        assert network.wifi_ssid == "MyWiFi"
        assert network.internet_reachable is True

    def test_network_info_mobile(self):
        network = NetworkInfo(
            wifi_connected=False,
            mobile_connected=True,
            mobile_type="LTE",
            mobile_ip="10.0.0.1",
            dns_servers=["8.8.8.8"],
            internet_reachable=True,
        )
        assert network.mobile_connected is True
        assert network.mobile_type == "LTE"


class TestThermalZone:
    """Tests for ThermalZone model."""

    def test_thermal_zone_creation(self):
        zone = ThermalZone(name="cpu0-thermal", temp_c=35.0, type="cpu")
        assert zone.name == "cpu0-thermal"
        assert zone.temp_c == 35.0
        assert zone.type == "cpu"
        assert zone.temp_f == 95.0


class TestThermalInfo:
    """Tests for ThermalInfo model."""

    def test_thermal_info_creation(self):
        thermal = ThermalInfo(
            zones=[
                ThermalZone(name="cpu0", temp_c=35.0, type="cpu"),
                ThermalZone(name="gpu", temp_c=40.0, type="gpu"),
            ],
            cpu_throttled=False,
            gpu_throttled=False,
            status=ThermalStatus.NORMAL,
        )
        assert len(thermal.zones) == 2
        assert thermal.cpu_throttled is False
        assert thermal.status == ThermalStatus.NORMAL


class TestMemoryInfo:
    """Tests for MemoryInfo model."""

    def test_memory_info_creation(self):
        from phone.models import MemoryInfo

        memory = MemoryInfo(
            total_kb=8_000_000,
            free_kb=2_000_000,
            available_kb=3_000_000,
            cached_kb=1_000_000,
            buffers_kb=500_000,
        )
        assert memory.total_kb == 8_000_000
        assert memory.total_mb == 8_000_000 / 1024
        assert memory.available_mb == 3_000_000 / 1024

    def test_usage_percent(self):
        from phone.models import MemoryInfo

        memory = MemoryInfo(
            total_kb=1000,
            free_kb=200,
            available_kb=300,
            cached_kb=100,
            buffers_kb=50,
        )
        # Usage = (total - available) / total * 100 = 70%
        assert memory.usage_percent == 70.0


class TestHealthReport:
    """Tests for HealthReport model."""

    def test_health_report_creation(self):
        from phone.models import (
            BatteryHealth,
            BatteryInfo,
            BatteryStatus,
            DeviceInfo,
            HealthReport,
            NetworkInfo,
            StorageInfo,
        )

        report = HealthReport(
            device=DeviceInfo(
                serial="RFCTA0AEKZP",
                model="SM-S906B",
                manufacturer="samsung",
                brand="samsung",
                device="o2s",
                product="o2sxxx",
                android_version="14",
                api_level=34,
                security_patch="2024-01-01",
                build_fingerprint="test",
                build_id="test",
                build_type="user",
                build_tags="release-keys",
            ),
            battery=BatteryInfo(
                level=75,
                health=BatteryHealth.GOOD,
                status=BatteryStatus.DISCHARGING,
                temperature_c=28.0,
                voltage_mv=4100,
                technology="Li-ion",
                plugged_type="Unknown",
            ),
            storage=[
                StorageInfo(
                    partition="/dev/block/dm-0",
                    total_bytes=5_000_000_000,
                    used_bytes=3_000_000_000,
                    free_bytes=2_000_000_000,
                    filesystem="f2fs",
                    mount_point="/data",
                )
            ],
            network=NetworkInfo(
                wifi_connected=True,
                internet_reachable=True,
            ),
        )

        assert report.device.model == "SM-S906B"
        assert report.battery.level == 75
        assert len(report.storage) == 1
        assert report.network.wifi_connected is True

    def test_is_healthy_property(self):
        from phone.models import HealthReport

        healthy_report = HealthReport(issues=[])
        assert healthy_report.is_healthy is True

        unhealthy_report = HealthReport(issues=["Battery critical"])
        assert unhealthy_report.is_healthy is False

    def test_summary_property(self):
        from phone.models import (
            BatteryHealth,
            BatteryInfo,
            BatteryStatus,
            DeviceInfo,
            HealthReport,
            NetworkInfo,
            StorageInfo,
        )

        report = HealthReport(
            device=DeviceInfo(
                serial="RFCTA0AEKZP",
                model="SM-S906B",
                manufacturer="samsung",
                brand="samsung",
                device="o2s",
                product="o2sxxx",
                android_version="14",
                api_level=34,
                security_patch="2024-01-01",
                build_fingerprint="test",
                build_id="test",
                build_type="user",
                build_tags="release-keys",
            ),
            battery=BatteryInfo(
                level=75,
                health=BatteryHealth.GOOD,
                status=BatteryStatus.DISCHARGING,
                temperature_c=28.0,
                voltage_mv=4100,
                technology="Li-ion",
                plugged_type="Unknown",
            ),
            storage=[
                StorageInfo(
                    partition="/dev/block/dm-0",
                    total_bytes=5_000_000_000,
                    used_bytes=3_000_000_000,
                    free_bytes=2_000_000_000,
                    filesystem="f2fs",
                    mount_point="/data",
                )
            ],
            network=NetworkInfo(
                wifi_connected=True,
                internet_reachable=True,
            ),
        )

        summary = report.summary
        assert "Battery: 75%" in summary
        assert "Storage:" in summary
        assert "Network: Online" in summary
