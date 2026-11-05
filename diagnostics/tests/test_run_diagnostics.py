"""Runner tests for diagnostics.run_diagnostics with a fully mocked device.

Restores the coverage lost with the OneDrive-casualty tests/ directory:
every check runs against mock phone modules, asserting checks report
pass/warning and never "error", and that the summary brands itself from
the detected model (multi-Galaxy compatibility).
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "phone-lib" / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from diagnostics import run_diagnostics as rd  # noqa: E402
from phone.models import (  # noqa: E402
    BatteryHealth,
    BatteryInfo,
    BatteryStatus,
    DeviceInfo,
    NetworkInfo,
    StorageInfo,
    ThermalInfo,
    ThermalStatus,
    ThermalZone,
)


def make_device_client() -> MagicMock:
    """A mock AdbClient whose module getters return real phone models."""
    client = MagicMock()
    client.serial = "TESTSERIAL123"
    return client


def patch_modules() -> dict[str, Any]:
    """MagicMock factories patched over the module-level names."""
    device = DeviceInfo(
        serial="TESTSERIAL123",
        model="SM-S906B",
        manufacturer="samsung",
        brand="samsung",
        device="o2s",
        product="o2sxxx",
        android_version="16",
        api_level=36,
        security_patch="2026-08-05",
        build_fingerprint="samsung/o2sxxx/o2s:16/TEST",
        build_id="TEST.000000.001",
        build_type="user",
        build_tags="release-keys",
    )
    battery = BatteryInfo(
        level=78,
        health=BatteryHealth.GOOD,
        status=BatteryStatus.CHARGING,
        temperature_c=29.5,
        voltage_mv=4123,
        current_ma=-350,
        charge_cycles=310,
        technology="Li-ion",
        plugged_type="USB",
    )
    network = NetworkInfo(
        wifi_connected=True,
        wifi_ssid="MyWiFiNetwork",
        wifi_signal_dbm=-45,
        internet_reachable=True,
    )
    thermal = ThermalInfo(
        zones=[ThermalZone(name="cpu0", temp_c=38.0, type="cpu")],
        cpu_throttled=False,
        gpu_throttled=False,
        status=ThermalStatus.NORMAL,
    )
    storage = [
        StorageInfo(
            partition="/dev/block/dm-0",
            mount_point="/data",
            total_bytes=225_000_000_000,
            used_bytes=100_000_000_000,
            free_bytes=125_000_000_000,
            filesystem="f2fs",
        )
    ]

    def module_with(**methods: Any) -> MagicMock:
        m = MagicMock()
        for name, value in methods.items():
            getattr(m, name).return_value = value
        return m

    return {
        "DeviceModule": module_with(get_device_info=device, is_rooted=False),
        "BatteryModule": module_with(get_battery_info=battery),
        "NetworkModule": module_with(get_network_info=network, test_dns_resolution=True),
        "ThermalModule": module_with(get_thermal_info=thermal),
        "StorageModule": module_with(get_storage_info=storage, find_large_files=[]),
        "LogcatModule": module_with(
            get_logs_with_stats={
                "filtered_logs": [],
                "stats": {
                    "false_positives": 0,
                    "total": 0,
                    "filter_rate": 0.0,
                    "false_positive_by_tag": {},
                },
            }
        ),
        "AppsModule": module_with(get_running_apps=[]),
    }


def make_runner(tmp_path: Path) -> rd.DiagnosticsRunner:
    runner = rd.DiagnosticsRunner(ROOT / "diagnostics" / "config.yaml")
    # keep the test hermetic: no repo log-file writes
    runner.output_root = tmp_path
    return runner


def run_with_mocks(runner: rd.DiagnosticsRunner, modules: dict[str, Any]) -> None:
    runner.client = make_device_client()
    with (
        patch.object(rd, "DeviceModule", return_value=modules["DeviceModule"]),
        patch.object(rd, "BatteryModule", return_value=modules["BatteryModule"]),
        patch.object(rd, "NetworkModule", return_value=modules["NetworkModule"]),
        patch.object(rd, "ThermalModule", return_value=modules["ThermalModule"]),
        patch.object(rd, "StorageModule", return_value=modules["StorageModule"]),
        patch.object(rd, "LogcatModule", return_value=modules["LogcatModule"]),
        patch.object(rd, "AppsModule", return_value=modules["AppsModule"]),
    ):
        runner.run_all_checks()


class TestRunnerChecks:
    def test_all_checks_pass_no_error(self, tmp_path: Path) -> None:
        runner = make_runner(tmp_path)
        run_with_mocks(runner, patch_modules())
        assert len(runner.results) == 7
        statuses = {r.status for r in runner.results}
        assert "error" not in statuses
        assert "pass" in statuses

    def test_summary_brands_from_detected_model(self, tmp_path: Path) -> None:
        """Multi-Galaxy: report header derives from the model, not a constant."""
        runner = make_runner(tmp_path)
        run_with_mocks(runner, patch_modules())
        report = runner.generate_report()
        summary = runner.format_summary(report)
        assert "Galaxy S22+ (SM-S906B)" in summary
        assert "Galaxy S22+ Health Report" not in summary  # old hardcode gone

    def test_empty_device_outputs_never_error(self, tmp_path: Path) -> None:
        """Older/sparse models: empty outputs degrade to warning, not error."""
        modules = patch_modules()
        # Minimal objects: everything empty/zeroed (defaults of the dataclasses)
        modules["DeviceModule"].get_device_info.return_value = DeviceInfo(
            serial="TESTSERIAL123",
            model="SM-UNKNOWN1",
            api_level=29,
            manufacturer="samsung",
            brand="samsung",
            device="unknown1",
            product="unknown1xx",
            android_version="10",
            security_patch="2026-01-01",
            build_fingerprint="samsung/unknown1/unknown1:10/TEST",
            build_id="TEST.000000.001",
            build_type="user",
            build_tags="release-keys",
        )
        modules["BatteryModule"].get_battery_info.return_value = BatteryInfo(
            level=0,
            health=BatteryHealth.UNKNOWN,
            status=BatteryStatus.UNKNOWN,
            temperature_c=0.0,
            voltage_mv=0,
            technology="unknown",
            plugged_type="Unknown",
        )
        modules["NetworkModule"].get_network_info.return_value = NetworkInfo(
            wifi_connected=False, mobile_connected=False
        )
        modules["ThermalModule"].get_thermal_info.return_value = ThermalInfo()
        modules["StorageModule"].get_storage_info.return_value = []
        modules["LogcatModule"].get_logs_with_stats.return_value = {
            "filtered_logs": [],
            "stats": {"false_positives": 0, "total": 0, "filter_rate": 0.0},
        }
        runner = make_runner(tmp_path)
        run_with_mocks(runner, modules)
        statuses = {r.status for r in runner.results}
        assert "error" not in statuses

    def test_report_roundtrip(self, tmp_path: Path) -> None:
        import json

        runner = make_runner(tmp_path)
        run_with_mocks(runner, patch_modules())
        report = runner.generate_report()
        payload = json.dumps(
            {**runner.__dict__, "report_timestamp": datetime.now().isoformat()},
            default=str,
        )
        assert "SM-S906B" in payload
        assert report.overall_status in ("healthy", "warning")


def test_report_path_template_rejects_escape() -> None:
    runner = rd.DiagnosticsRunner(ROOT / "diagnostics" / "config.yaml")
    with pytest.raises(ValueError):
        runner._validate_template("../escape.json")
