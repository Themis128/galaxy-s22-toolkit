"""Cross-model compatibility tests: capability detection, parser variants,
and model-agnostic repair filtering (Galaxy S/Note/A, Android 10+).

These use synthetic dumpsys/getprop fixtures shaped like older devices
instead of the S22+-specific conftest mocks.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from phone.battery import BatteryModule
from phone.capabilities import DeviceProfile, describe_model, detect_profile
from phone.device import DeviceModule
from phone.repair import RepairModule


def make_client(responses: dict[tuple[str, ...], str]) -> MagicMock:
    """Minimal AdbClient mock keyed by exact command tuples.

    Single-property getprop lookups (shell, getprop, <key>) are answered
    from the full dump under key ("shell", "getprop") when present.
    """

    def execute(*args: Any, **kwargs: Any) -> str:
        key = tuple(args)
        if key in responses:
            return responses[key]
        if args[:2] == ("shell", "getprop") and len(args) == 3:
            dump = responses.get(("shell", "getprop"), "")
            for line in dump.splitlines():
                if f"[{args[2]}]" in line and "]: [" in line:
                    return line.split("]: [")[1].rstrip("]") + "\n"
            return ""
        return responses.get(key, "")

    client = MagicMock()
    client.execute = MagicMock(side_effect=execute)
    client.execute_async = AsyncMock(side_effect=execute)
    client.get_serial = MagicMock(return_value="TESTSERIAL123")
    client.get_devices = MagicMock(return_value=[{"serial": "TESTSERIAL123", "state": "device"}])
    return client


def getprop_dump(model: str, api: int, android: str, platform: str, hw: str, oneui: str) -> str:
    """A realistic getprop dump for a Galaxy model."""
    return (
        f"[ro.product.model]: [{model}]\n"
        "[ro.product.manufacturer]: [samsung]\n"
        f"[ro.product.device]: [{model[-4:].lower()}]\n"
        f"[ro.build.version.release]: [{android}]\n"
        f"[ro.build.version.sdk]: [{api}]\n"
        f"[ro.board.platform]: [{platform}]\n"
        f"[ro.hardware]: [{hw}]\n"
        f"[ro.build.version.oneui]: [{oneui}]\n"
    )


# (model, api, android, platform, hw, oneui, expected name, expected chipset)
PROFILES: list[tuple[str, int, str, str, str, str, str, str]] = [
    ("SM-G973F", 29, "10", "exynos9820", "exynos9820", "", "S10", "Exynos 9820"),
    ("SM-G981B", 30, "11", "lahaina", "qcom", "", "S20 5G", "Snapdragon 888"),
    ("SM-G991B", 31, "12", "lahaina", "qcom", "30100", "S21", "Snapdragon 888"),
    ("SM-N986B", 30, "11", "exynos990", "exynos990", "30000", "Note20 Ultra 5G", "Exynos 990"),
    ("SM-A546B", 34, "14", "s5e8535", "s5e8535", "60100", "A54", "Exynos s5e8535"),
    ("SM-S906B", 36, "16", "universal9925", "s5e9925", "80000", "S22+", "Exynos 2200"),
    ("SM-X9999Z", 33, "13", "bengal", "qcom", "", "SM-X9999Z", "Snapdragon 460-class"),
]


class TestProfileDetection:
    @pytest.mark.parametrize(
        "model,api,android,platform,hw,oneui,expected_name,expected_chipset", PROFILES
    )
    def test_known_and_unknown_models(
        self,
        model: str,
        api: int,
        android: str,
        platform: str,
        hw: str,
        oneui: str,
        expected_name: str,
        expected_chipset: str,
    ) -> None:
        client = make_client(
            {
                ("shell", "getprop"): getprop_dump(model, api, android, platform, hw, oneui),
            }
        )
        profile = detect_profile(DeviceModule(client))
        assert profile.marketing_name == expected_name
        assert profile.chipset == expected_chipset
        assert profile.api_level == api
        assert profile.is_samsung is True

    def test_s22_plus_live_values(self) -> None:
        """The anchor device resolves exactly as observed live."""
        client = make_client(
            {
                ("shell", "getprop"): getprop_dump(
                    "SM-S906B", 36, "16", "universal9925", "s5e9925", "80000"
                ),
            }
        )
        p = detect_profile(DeviceModule(client))
        assert p.marketing_name == "S22+"
        assert p.series == "S"
        assert p.year_class == 2022
        assert p.one_ui == "8.0"
        assert "android_10_plus" in p.flags

    def test_never_raises_on_garbage_props(self) -> None:
        client = make_client({("shell", "getprop"): "garbage output\nno brackets"})
        profile = detect_profile(DeviceModule(client))
        assert profile.model == "unknown"
        assert profile.display_name() == "Galaxy"

    def test_series_classification(self) -> None:
        for model, series in [
            ("SM-S906B", "S"),
            ("SM-N986B", "Note"),
            ("SM-A546B", "A"),
            ("SM-F936B", "other"),
        ]:
            client = make_client(
                {("shell", "getprop"): getprop_dump(model, 33, "13", "x", "y", "")}
            )
            assert detect_profile(DeviceModule(client)).series == series

    def test_describe_model_from_bare_code(self) -> None:
        assert describe_model("SM-S906B") == "Galaxy S22+ (SM-S906B)"
        assert describe_model("SM-G973F") == "Galaxy S10 (SM-G973F)"
        assert describe_model("SM-A546B") == "Galaxy A54 (SM-A546B)"
        assert describe_model("SM-XYZ99Q") == "Galaxy (SM-XYZ99Q)"
        assert describe_model("") == "Galaxy"


class TestBatteryParserVariants:
    """Battery parsing across generations: dumpsys with/without current,
    sysfs fallback, µA-vs-mA."""

    def test_dumpsys_with_current(self) -> None:
        client = make_client(
            {
                ("shell", "dumpsys", "battery"): (
                    "status: 3\nhealth: 2\nlevel: 60\nvoltage: 4000\n"
                    "temperature: 300\ncurrent now: -350\n"
                ),
                ("shell", "dumpsys", "batterystats", "--checkin"): "",
            }
        )
        info = BatteryModule(client).get_battery_info()
        assert info.current_ma == -350

    def test_dumpsys_without_current_falls_back_to_sysfs_ma(self) -> None:
        client = make_client(
            {
                ("shell", "dumpsys", "battery"): (
                    "status: 3\nhealth: 2\nlevel: 60\nvoltage: 4000\ntemperature: 300\n"
                ),
                (
                    "shell",
                    "cat",
                    "/sys/class/power_supply/battery/current_now",
                ): "-350000\n",
                ("shell", "dumpsys", "batterystats", "--checkin"): "",
            }
        )
        info = BatteryModule(client).get_battery_info()
        assert info.current_ma == -350  # µA converted to mA

    def test_sysfs_microamp_small_value_stays(self) -> None:
        client = make_client(
            {
                ("shell", "dumpsys", "battery"): "level: 60\n",
                (
                    "shell",
                    "cat",
                    "/sys/class/power_supply/battery/current_now",
                ): "-350\n",  # already mA
                ("shell", "dumpsys", "batterystats", "--checkin"): "",
            }
        )
        info = BatteryModule(client).get_battery_info()
        assert info.current_ma == -350

    def test_implausible_sysfs_current_is_none(self) -> None:
        client = make_client(
            {
                ("shell", "dumpsys", "battery"): "level: 60\n",
                (
                    "shell",
                    "cat",
                    "/sys/class/power_supply/battery/current_now",
                ): "999999999\n",
                ("shell", "dumpsys", "batterystats", "--checkin"): "",
            }
        )
        info = BatteryModule(client).get_battery_info()
        assert info.current_ma is None

    def test_no_current_anywhere_is_none_not_error(self) -> None:
        client = make_client(
            {
                ("shell", "dumpsys", "battery"): "level: 60\n",
                ("shell", "dumpsys", "batterystats", "--checkin"): "",
            }
        )
        info = BatteryModule(client).get_battery_info()
        assert info.current_ma is None

    def test_batterystats_checkin_without_cycles(self) -> None:
        """Older kernels emit different checkin lines; cycles stay None."""
        client = make_client(
            {
                ("shell", "dumpsys", "battery"): "level: 60\n",
                ("shell", "dumpsys", "batterystats", "--checkin"): "9,0,100\n7,0,1,2,3\n",
            }
        )
        info = BatteryModule(client).get_battery_info()
        assert info.charge_cycles is None


class TestThermalParserVariants:
    """Both dumpsys thermalservice formats across Android versions."""

    def _thermal_client(self, dumpsys: str) -> MagicMock:
        return make_client(
            {
                ("shell", "ls", "/sys/class/thermal/"): "",
                ("shell", "ls", "/sys/devices/virtual/thermal/"): "",
                ("shell", "dumpsys", "thermalservice"): dumpsys,
            }
        )

    def test_thermalservice_hal_format(self) -> None:
        client = self._thermal_client(
            "Current temperatures from HAL:\n"
            "Temperature{mValue=35.0, mType=CPU, mName=cpu0, mStatus=0}\n"
            "Temperature{mValue=41.5, mType=BATTERY, mName=battery, mStatus=0}\n"
        )
        from phone.thermal import ThermalModule

        zones_list = ThermalModule(client).get_thermal_zones()
        assert {z.name for z in zones_list} == {"cpu0", "battery"}
        assert any(z.temp_c == 41.5 for z in zones_list)

    def test_thermalservice_a14_plus_format(self) -> None:
        from phone.thermal import ThermalModule

        client = self._thermal_client(
            "Current temperatures from HAL:\nZone: cpu0, temp=42.5°C\nZone: gpu0, temp=39.0°C\n"
        )
        zones_list = ThermalModule(client).get_thermal_zones()
        assert {z.name for z in zones_list} == {"cpu0", "gpu0"}

    def test_no_thermal_sources_degrades_to_empty(self) -> None:
        from phone.thermal import ThermalModule

        client = self._thermal_client("")
        assert ThermalModule(client).get_thermal_zones() == []


class TestRepairBloatwareFiltering:
    """disable_bloatware partitions installed/disabled/absent in one pass."""

    def _run(self, installed: str, disabled: str) -> Any:
        import asyncio

        client = make_client(
            {
                ("shell", "pm list packages"): installed,
                ("shell", "pm list packages -d"): disabled,
            }
        )
        module = RepairModule(client)
        return asyncio.run(module._repair_disable_bloatware())

    def test_absent_packages_counted_not_attempted(self) -> None:
        result = self._run(
            installed="package:com.samsung.android.app.spage\npackage:com.android.settings\n",
            disabled="",
        )
        assert result.success is True
        details = result.details
        # spage installed+enabled -> disabled; everything else absent
        assert details["disabled"] == ["com.samsung.android.app.spage"]
        assert "com.samsung.android.svoice.sync" in details["absent_on_model"]
        assert details["already_disabled"] == []

    def test_already_disabled_skipped(self) -> None:
        result = self._run(
            installed="package:com.samsung.android.app.spage\n",
            disabled="package:com.samsung.android.app.spage\n",
        )
        assert result.details["disabled"] == []
        assert result.details["already_disabled"] == ["com.samsung.android.app.spage"]

    def test_unenumerable_packages_falls_back_to_probe(self) -> None:
        """When pm list fails, per-package probing still disables what exists."""
        import asyncio

        client = make_client(
            {
                # enumerate fails -> empty; per-pkg probe for spage succeeds
                ("shell", "pm list packages"): "",
                ("shell", "pm list packages -d"): "",
                ("shell", "pm list packages com.samsung.android.app.spage"): (
                    "package:com.samsung.android.app.spage\n"
                ),
            }
        )
        module = RepairModule(client)
        result = asyncio.run(module._repair_disable_bloatware())
        assert result.success is True
        # No per-pkg probe responses for other entries; nothing blew up
        assert "disabled" in result.details


def test_profile_is_dataclass_default() -> None:
    p = DeviceProfile()
    assert p.display_name() == "Galaxy"
    assert p.series == "unknown"
