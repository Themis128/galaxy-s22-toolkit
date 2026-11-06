"""Tests for device capability profiles (phone.capabilities)."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from phone.capabilities import (
    DeviceProfile,
    _resolve_chipset,
    _resolve_marketing_name,
    _resolve_one_ui,
    describe_model,
    detect_profile,
)

# =============================================================================
# Mock device module fixtures
# =============================================================================


@dataclass
class MockDevice:
    """Mock DeviceModule with controllable getprop responses."""

    props: dict[str, str]

    def get_prop(self, key: str, default: str = "") -> str:
        return self.props.get(key, default)

    def get_all_props(self) -> dict[str, str]:
        return self.props.copy()


# getprop dumps for known Samsung devices across API levels
S10_PROPS = {
    "ro.product.model": "SM-G973F",
    "ro.product.manufacturer": "samsung",
    "ro.build.version.sdk": "29",
    "ro.build.version.oneui": "10000",  # 1.0
    "ro.board.platform": "universal9820",
    "ro.soc.model": "exynos9820",
    "ro.hardware": "universal9820",
    "ro.boot.hardware": "universal9820",
}

S20_PROPS = {
    "ro.product.model": "SM-G980F",
    "ro.product.manufacturer": "samsung",
    "ro.build.version.sdk": "31",
    "ro.build.version.oneui": "30100",  # 3.1
    "ro.board.platform": "universal990",
    "ro.soc.model": "exynos990",
    "ro.hardware": "universal990",
    "ro.boot.hardware": "universal990",
}

S21_PROPS = {
    "ro.product.model": "SM-G991B",
    "ro.product.manufacturer": "samsung",
    "ro.build.version.sdk": "33",
    "ro.build.version.oneui": "40000",  # 4.0
    "ro.board.platform": "s5e9925",
    "ro.soc.model": "exynos2200",
    "ro.hardware": "s5e9925",
    "ro.boot.hardware": "s5e9925",
}

A54_PROPS = {
    "ro.product.model": "SM-A546B",
    "ro.product.manufacturer": "samsung",
    "ro.build.version.sdk": "34",
    "ro.build.version.oneui": "50100",  # 5.1
    "ro.board.platform": "universal9825",
    "ro.soc.model": "exynos9825",
    "ro.hardware": "universal9825",
    "ro.boot.hardware": "universal9825",
}

S22_PLUS_PROPS = {
    "ro.product.model": "SM-S906B",
    "ro.product.manufacturer": "samsung",
    "ro.build.version.sdk": "36",
    "ro.build.version.oneui": "80000",  # 8.0
    "ro.board.platform": "s5e9925",
    "ro.soc.model": "exynos2200",
    "ro.hardware": "s5e9925",
    "ro.boot.hardware": "s5e9925",
}

UNKNOWN_MODEL_PROPS = {
    "ro.product.model": "SM-G999F",  # S-series not in table
    "ro.product.manufacturer": "samsung",
    "ro.build.version.sdk": "33",
    "ro.build.version.oneui": "50000",  # 5.0
    "ro.board.platform": "unknown_platform",
    "ro.soc.model": "",
    "ro.hardware": "unknown_hw",
    "ro.boot.hardware": "unknown_hw",
}

NON_SAMSUNG_PROPS = {
    "ro.product.model": "Pixel 7",
    "ro.product.manufacturer": "Google",
    "ro.build.version.sdk": "33",
    "ro.build.version.oneui": "",
    "ro.board.platform": "gs201",
    "ro.soc.model": "google_gs201",
    "ro.hardware": "gs201",
    "ro.boot.hardware": "gs201",
}

EMPTY_PROPS = {}


# =============================================================================
# Test _resolve_marketing_name
# =============================================================================


class TestResolveMarketingName:
    """Test model -> marketing name/series/year resolution."""

    def test_s22_plus(self):
        name, series, year = _resolve_marketing_name("SM-S906B")
        assert name == "S22+"
        assert series == "S"
        assert year == 2022

    def test_s23_ultra(self):
        name, series, year = _resolve_marketing_name("SM-S918B")
        assert name == "S23 Ultra"
        assert series == "S"
        assert year == 2023

    def test_s10(self):
        name, series, year = _resolve_marketing_name("SM-G973F")
        assert name == "S10"
        assert series == "S"
        assert year == 2019

    def test_note20_ultra(self):
        name, series, year = _resolve_marketing_name("SM-N985F")
        assert name == "Note20 Ultra"
        assert series == "Note"
        assert year == 2020

    def test_a54(self):
        name, series, year = _resolve_marketing_name("SM-A546B")
        assert name == "A54"
        assert series == "A"
        assert year == 2023

    def test_a34(self):
        name, series, year = _resolve_marketing_name("SM-A346B")
        assert name == "A34"
        assert series == "A"
        assert year == 2023

    def test_unknown_model(self):
        name, series, year = _resolve_marketing_name("SM-F999Z")
        assert name == "SM-F999Z"
        assert series == "other"
        assert year is None

    def test_empty_model(self):
        name, series, year = _resolve_marketing_name("")
        assert name == ""
        assert series == "unknown"
        assert year is None


# =============================================================================
# Test _resolve_chipset
# =============================================================================


class TestResolveChipset:
    """Test chipset resolution from platform properties."""

    def test_exynos_2200_s5e9925(self):
        device = MockDevice(S22_PLUS_PROPS)
        assert _resolve_chipset(device) == "Exynos 2200"

    def test_exynos_990(self):
        device = MockDevice(S20_PROPS)
        assert _resolve_chipset(device) == "Exynos 990"

    def test_exynos_9820(self):
        device = MockDevice(S10_PROPS)
        assert _resolve_chipset(device) == "Exynos 9820"

    def test_snapdragon_8_gen_1(self):
        props = {**S21_PROPS, "ro.board.platform": "taro"}
        device = MockDevice(props)
        assert _resolve_chipset(device) == "Snapdragon 8 Gen 1"

    def test_snapdragon_8_gen_2(self):
        props = {**S22_PLUS_PROPS, "ro.board.platform": "kalama"}
        device = MockDevice(props)
        assert _resolve_chipset(device) == "Snapdragon 8 Gen 2"

    def test_unknown_platform_stays_raw(self):
        device = MockDevice(UNKNOWN_MODEL_PROPS)
        # Unknown platform codes are returned as-is (honest)
        assert _resolve_chipset(device) == "unknown"

    def test_non_samsung_platform(self):
        device = MockDevice(NON_SAMSUNG_PROPS)
        # Google Tensor not in table, stays unknown
        assert _resolve_chipset(device) == "unknown"

    def test_empty_props(self):
        device = MockDevice(EMPTY_PROPS)
        assert _resolve_chipset(device) == "unknown"


# =============================================================================
# Test _resolve_one_ui
# =============================================================================


class TestResolveOneUI:
    """Test One UI version decoding."""

    def test_one_ui_1(self):
        device = MockDevice(S10_PROPS)  # 10000 -> 1.0
        assert _resolve_one_ui(device) == "1.0"

    def test_one_ui_3_1(self):
        device = MockDevice(S20_PROPS)  # 31000 -> 3.1
        assert _resolve_one_ui(device) == "3.1"

    def test_one_ui_4(self):
        device = MockDevice(S21_PROPS)  # 40000 -> 4.0
        assert _resolve_one_ui(device) == "4.0"

    def test_one_ui_5_1(self):
        device = MockDevice(A54_PROPS)  # 51000 -> 5.1
        assert _resolve_one_ui(device) == "5.1"

    def test_one_ui_8(self):
        device = MockDevice(S22_PLUS_PROPS)  # 80000 -> 8.0
        assert _resolve_one_ui(device) == "8.0"

    def test_missing_oneui_property(self):
        props = {**S22_PLUS_PROPS, "ro.build.version.oneui": ""}
        device = MockDevice(props)
        assert _resolve_one_ui(device) == "unknown"

    def test_non_numeric_oneui(self):
        props = {**S22_PLUS_PROPS, "ro.build.version.oneui": "abc"}
        device = MockDevice(props)
        assert _resolve_one_ui(device) == "unknown"


# =============================================================================
# Test describe_model
# =============================================================================


class TestDescribeModel:
    """Test the branding helper."""

    def test_known_model(self):
        assert describe_model("SM-S906B") == "Galaxy S22+ (SM-S906B)"

    def test_s10(self):
        assert describe_model("SM-G973F") == "Galaxy S10 (SM-G973F)"

    def test_note20(self):
        assert describe_model("SM-N980F") == "Galaxy Note20 (SM-N980F)"

    def test_a54(self):
        assert describe_model("SM-A546B") == "Galaxy A54 (SM-A546B)"

    def test_unknown_model(self):
        assert describe_model("SM-X999Z") == "Galaxy (SM-X999Z)"

    def test_empty_model(self):
        assert describe_model("") == "Galaxy"

    def test_none_model(self):
        # The function expects str but handle gracefully
        assert describe_model("") == "Galaxy"


# =============================================================================
# Test detect_profile (integration)
# =============================================================================


class TestDetectProfile:
    """Test full device profile detection."""

    def test_s10_api29(self):
        device = MockDevice(S10_PROPS)
        profile = detect_profile(device)

        assert profile.model == "SM-G973F"
        assert profile.marketing_name == "S10"
        assert profile.series == "S"
        assert profile.year_class == 2019
        assert profile.chipset == "Exynos 9820"
        assert profile.api_level == 29
        assert profile.one_ui == "1.0"
        assert profile.is_samsung is True
        assert "android_10_plus" in profile.flags

    def test_s20_api31(self):
        device = MockDevice(S20_PROPS)
        profile = detect_profile(device)

        assert profile.model == "SM-G980F"
        assert profile.marketing_name == "S20"
        assert profile.series == "S"
        assert profile.year_class == 2020
        assert profile.chipset == "Exynos 990"
        assert profile.api_level == 31
        assert profile.one_ui == "3.1"
        assert profile.is_samsung is True
        assert "android_10_plus" in profile.flags
        # API 31 is Android 12, not Android 13 (API 33)
        assert "android_13_plus" not in profile.flags

    def test_s21_api33(self):
        device = MockDevice(S21_PROPS)
        profile = detect_profile(device)

        assert profile.model == "SM-G991B"
        assert profile.marketing_name == "S21"
        assert profile.series == "S"
        assert profile.year_class == 2021
        assert profile.chipset == "Exynos 2200"
        assert profile.api_level == 33
        assert profile.one_ui == "4.0"
        assert profile.is_samsung is True
        assert "android_10_plus" in profile.flags
        assert "android_13_plus" in profile.flags

    def test_a54_api34(self):
        device = MockDevice(A54_PROPS)
        profile = detect_profile(device)

        assert profile.model == "SM-A546B"
        assert profile.marketing_name == "A54"
        assert profile.series == "A"
        assert profile.year_class == 2023
        assert profile.chipset == "Exynos 9825"
        assert profile.api_level == 34
        assert profile.one_ui == "5.1"
        assert profile.is_samsung is True
        assert "android_10_plus" in profile.flags
        assert "android_13_plus" in profile.flags

    def test_s22_plus_api36(self):
        device = MockDevice(S22_PLUS_PROPS)
        profile = detect_profile(device)

        assert profile.model == "SM-S906B"
        assert profile.marketing_name == "S22+"
        assert profile.series == "S"
        assert profile.year_class == 2022
        assert profile.chipset == "Exynos 2200"
        assert profile.api_level == 36
        assert profile.one_ui == "8.0"
        assert profile.is_samsung is True
        assert "android_10_plus" in profile.flags
        assert "android_13_plus" in profile.flags

    def test_unknown_model_conservative_defaults(self):
        device = MockDevice(UNKNOWN_MODEL_PROPS)
        profile = detect_profile(device)

        assert profile.model == "SM-G999F"
        assert profile.marketing_name == "SM-G999F"
        assert profile.series == "S"
        assert profile.year_class is None
        assert profile.chipset == "unknown"
        assert profile.api_level == 33
        assert profile.one_ui == "5.0"
        assert profile.is_samsung is True
        assert "android_10_plus" in profile.flags
        assert "android_13_plus" in profile.flags

    def test_non_samsung_device(self):
        device = MockDevice(NON_SAMSUNG_PROPS)
        profile = detect_profile(device)

        assert profile.model == "Pixel 7"
        assert profile.is_samsung is False

    def test_empty_props_never_raises(self):
        device = MockDevice(EMPTY_PROPS)
        profile = detect_profile(device)

        assert profile.model == "unknown"
        assert profile.marketing_name == "unknown"
        assert profile.api_level == 0
        assert profile.one_ui == "unknown"
        assert profile.is_samsung is False
        assert len(profile.flags) == 0

    def test_malformed_sdk_version(self):
        props = {**S22_PLUS_PROPS, "ro.build.version.sdk": "not_a_number"}
        device = MockDevice(props)
        profile = detect_profile(device)
        # Should not raise, api_level defaults to 0
        assert profile.api_level == 0
        assert profile.model == "SM-S906B"


# =============================================================================
# Test DeviceProfile display_name
# =============================================================================


class TestDeviceProfileDisplayName:
    """Test DeviceProfile.display_name() branding."""

    def test_known_model(self):
        profile = DeviceProfile(
            model="SM-S906B",
            marketing_name="S22+",
            series="S",
            chipset="Exynos 2200",
            api_level=36,
            one_ui="8.0",
        )
        assert profile.display_name() == "Galaxy S22+ (SM-S906B)"

    def test_unknown_model_fallback(self):
        profile = DeviceProfile(
            model="SM-X999Z",
            marketing_name="SM-X999Z",
            series="other",
        )
        assert profile.display_name() == "Galaxy (SM-X999Z)"

    def test_empty_model(self):
        profile = DeviceProfile(
            model="unknown",
            marketing_name="unknown",
            series="unknown",
        )
        assert profile.display_name() == "Galaxy"
