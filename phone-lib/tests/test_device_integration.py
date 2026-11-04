"""Integration tests against the physical phone.

These run read-only checks only. They are skipped automatically when no
device is attached:

    pytest tests -m device        # locally, phone connected
    pytest -m "not device"        # CI (no hardware)
"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.device

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_wireless_config() -> dict | None:
    """Load device.wireless_adb from the toolkit config, like production code."""
    cfg_path = REPO_ROOT / "diagnostics" / "config.yaml"
    if not cfg_path.exists():
        return None
    try:
        import yaml

        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        return (data.get("device") or {}).get("wireless_adb")
    except Exception:
        return None


@pytest.fixture(scope="module")
def client():
    """Connect exactly like the toolkit does (config -> pin -> auto-connect)."""
    from phone import create_client

    c = create_client(wireless=_load_wireless_config())
    # Bare create_client with two transports and no preference yields
    # serial=None, which fails every command with "more than one device".
    if getattr(c, "serial", None) is None:
        import subprocess

        try:
            out = subprocess.run(
                ["adb", "devices"], capture_output=True, text=True, timeout=10
            ).stdout
        except Exception:
            pytest.skip("adb not available")
        serials = [
            parts[0]
            for line in out.splitlines()[1:]
            if len(parts := line.split()) >= 2 and parts[1] == "device"
        ]
        if not serials:
            pytest.skip("no device attached")
        usb = [s for s in serials if ":" not in s]
        c = create_client(serial=usb[0] if usb else serials[0])
    return c


class TestDeviceInfo:
    def test_model_is_galaxy_s22_plus(self, client):
        info = client.device.get_device_info()
        assert "SM-S906" in info.model

    def test_android_version_current(self, client):
        info = client.device.get_device_info()
        assert info.api_level >= 34

    def test_all_props_populated(self, client):
        props = client.device.get_all_props()
        assert props.get("ro.product.model") == "SM-S906B"


class TestBattery:
    def test_level_plausible(self, client):
        battery = client.battery.get_battery_info()
        assert 0 < battery.level <= 100

    def test_temperature_c_plausible(self, client):
        battery = client.battery.get_battery_info()
        assert 10.0 <= battery.temperature_c <= 60.0


class TestStorage:
    def test_storage_totals_sane(self, client):
        storages = client.storage.get_storage_info()
        total = sum(s.total_bytes for s in storages)
        used = sum(s.used_bytes for s in storages)
        assert total > 0
        assert 0 <= used <= total


class TestLogcat:
    def test_recent_logs_readable(self, client):
        from phone.logcat import LogcatModule

        logs = LogcatModule(client).get_logs(lines=5)
        assert isinstance(logs, list)
