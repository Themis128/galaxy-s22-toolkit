"""Unit tests for phone.imobile (hermetic — no device, no libimobiledevice)."""

from __future__ import annotations

import pytest

from phone.exceptions import PhoneError
from phone.imobile import parse_ideviceinfo

SAMPLE_INFO = """\
ActivationState: Activated
DeviceName: iPhone
ProductType: iPhone15,2
ProductVersion: 18.1
SerialNumber: F2LX1234
UniqueDeviceID: 00008101-000A1234
somekeywithempty: """


class TestParseIdeviceinfo:
    def test_parses_keys(self) -> None:
        props = parse_ideviceinfo(SAMPLE_INFO)
        assert props["DeviceName"] == "iPhone"
        assert props["ProductType"] == "iPhone15,2"
        assert props["ProductVersion"] == "18.1"
        assert props["UniqueDeviceID"] == "00008101-000A1234"

    def test_ignores_blank_and_empty_values(self) -> None:
        props = parse_ideviceinfo(SAMPLE_INFO)
        assert props.get("somekeywithempty") == ""

    def test_ignores_lines_without_colon(self) -> None:
        assert parse_ideviceinfo("no colon here\nkey: value") == {"key": "value"}

    def test_empty_input(self) -> None:
        assert parse_ideviceinfo("") == {}


class TestIMobileClientUnavailable:
    def test_missing_binary_raises_phone_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import phone.imobile as im

        monkeypatch.setattr(im.shutil, "which", lambda _: None)
        with pytest.raises(PhoneError, match="not installed"):
            im._run(["ideviceinfo"])

    def test_no_device_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import phone.imobile as im

        monkeypatch.setattr(im, "list_udids", lambda: [])
        from phone.imobile import IMobileClient

        with pytest.raises(PhoneError, match="No iOS device"):
            IMobileClient()
