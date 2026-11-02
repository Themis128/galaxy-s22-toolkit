"""Unit tests for device module."""

from __future__ import annotations

from phone.device import DeviceModule
from phone.models import DeviceInfo


class TestDeviceModule:
    """Tests for DeviceModule."""

    def test_get_device_info(self, mock_adb_client):
        """Test getting full device info."""
        module = DeviceModule(mock_adb_client)
        device = module.get_device_info()

        assert isinstance(device, DeviceInfo)
        assert device.model == "SM-S906B"
        assert device.manufacturer == "samsung"
        assert device.brand == "samsung"
        assert device.device == "o2s"
        assert device.product == "o2sxxx"
        assert device.android_version == "14"
        assert device.api_level == 34
        assert device.security_patch == "2024-01-01"
        assert "samsung/o2sxxx/o2s:14/UP1A.231005.007" in device.build_fingerprint
        assert device.build_id == "UP1A.231005.007"
        assert device.build_type == "user"
        assert device.build_tags == "release-keys"
        assert device.kernel_version == "5.15.100-12345678"
        assert device.bootloader == "S906BXXU2BWK1"
        assert device.hardware == "qcom"
        assert device.cpu_abi == "arm64-v8a"
        assert device.cpu_abi2 == ""
        assert device.screen_density == 420

    def test_get_all_props(self, mock_adb_client):
        """Test getting all properties."""
        module = DeviceModule(mock_adb_client)
        props = module.get_all_props()

        assert "ro.product.model" in props
        assert props["ro.product.model"] == "SM-S906B"
        assert "ro.build.version.release" in props
        assert props["ro.build.version.release"] == "14"
        assert "ro.build.version.sdk" in props
        assert props["ro.build.version.sdk"] == "34"

    def test_get_prop(self, mock_adb_client):
        """Test getting a single property."""
        module = DeviceModule(mock_adb_client)

        model = module.get_prop("ro.product.model")
        assert model == "SM-S906B"

        android_version = module.get_prop("ro.build.version.release")
        assert android_version == "14"

        # Non-existent property
        unknown = module.get_prop("ro.nonexistent")
        assert unknown is None

    def test_get_android_version(self, mock_adb_client):
        """Test getting Android version."""
        module = DeviceModule(mock_adb_client)
        version = module.get_android_version()
        assert version == "14"

    def test_get_api_level(self, mock_adb_client):
        """Test getting API level."""
        module = DeviceModule(mock_adb_client)
        api = module.get_api_level()
        assert api == 34

    def test_get_security_patch(self, mock_adb_client):
        """Test getting security patch date."""
        module = DeviceModule(mock_adb_client)
        patch = module.get_security_patch()
        assert patch == "2024-01-01"

    def test_get_build_fingerprint(self, mock_adb_client):
        """Test getting build fingerprint."""
        module = DeviceModule(mock_adb_client)
        fingerprint = module.get_build_fingerprint()
        assert "samsung/o2sxxx/o2s:14/UP1A.231005.007" in fingerprint

    def test_is_rooted(self, mock_adb_client):
        """Test checking if device is rooted."""
        module = DeviceModule(mock_adb_client)

        # Default mock doesn't have su, so should return False
        is_rooted = module.is_rooted()
        assert is_rooted is False

    def test_get_cpu_info(self, mock_adb_client):
        """Test getting CPU info."""
        mock_adb_client.execute.return_value = """Processor	: AArch64 Processor rev 2 (aarch64)
processor	: 0
BogoMIPS	: 38.00

processor	: 1
BogoMIPS	: 38.00

processor	: 2
BogoMIPS	: 38.00

processor	: 3
BogoMIPS	: 38.00

processor	: 4
BogoMIPS	: 38.00

processor	: 5
BogoMIPS	: 38.00

processor	: 6
BogoMIPS	: 38.00

processor	: 7
BogoMIPS	: 38.00

Features	: fp asimd evtstrm crc32 cpuid
CPU implementer	: 0x41
CPU architecture: 8
CPU variant	: 0x1
CPU part	: 0xd47
CPU revision	: 2
"""
        module = DeviceModule(mock_adb_client)
        cpu = module.get_cpu_info()

        assert cpu["count"] == 8
        assert len(cpu["details"]) == 8

    def test_get_memory_info(self, mock_adb_client):
        """Test getting memory info."""
        mock_adb_client.execute.return_value = """MemTotal:        8000000 kB
MemFree:          2000000 kB
MemAvailable:     3000000 kB
Buffers:           500000 kB
Cached:           1000000 kB
SwapCached:            0 kB
Active:           2000000 kB
Inactive:         1000000 kB
Active(anon):     1500000 kB
Inactive(anon):    500000 kB
Active(file):      500000 kB
Inactive(file):    500000 kB
Unevictable:           0 kB
Mlocked:               0 kB
SwapTotal:             0 kB
SwapFree:              0 kB
"""
        module = DeviceModule(mock_adb_client)
        memory = module.get_memory_info()

        assert memory["MemTotal"] == 8000000
        assert memory["MemFree"] == 2000000
        assert memory["MemAvailable"] == 3000000
        assert memory["Buffers"] == 500000
        assert memory["Cached"] == 1000000
        assert memory["SwapTotal"] == 0
        assert memory["SwapFree"] == 0
