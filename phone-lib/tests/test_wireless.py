"""Unit tests for create_client wireless auto-connect and serial resolution."""

from __future__ import annotations

import pytest

import phone.adb as adb_mod
from phone.adb import create_client


class FakeAdb:
    """Stands in for every AdbClient construction inside create_client."""

    instances: list[FakeAdb] = []
    start_empty = False  # class switch: whether a device is attached initially

    def __init__(self, serial=None, **kwargs):
        self.serial = serial
        self.connect_calls: list[str] = []
        self.devices = [] if FakeAdb.start_empty else [{"serial": "RFCTA0AEKZP", "state": "device"}]
        FakeAdb.instances.append(self)

    def list_devices(self):
        return self.devices

    def execute(self, *args, **kwargs):
        self.connect_calls.append(" ".join(str(a) for a in args))
        self.devices.append({"serial": "100.84.31.85:5555", "state": "device"})
        return "connected"


@pytest.fixture(autouse=True)
def _fake_adb(monkeypatch):
    monkeypatch.setattr(adb_mod, "AdbClient", FakeAdb)
    FakeAdb.instances = []
    FakeAdb.start_empty = False
    monkeypatch.delenv("PHONE_ADB_SERIAL", raising=False)
    yield


def _connect_calls() -> list[str]:
    return [c for inst in FakeAdb.instances for c in inst.connect_calls]


class TestCreateClientResolution:
    def test_explicit_serial_never_connects(self):
        client = create_client(serial="XYZ")
        assert client.serial == "XYZ"
        assert _connect_calls() == []

    def test_env_serial_never_connects(self, monkeypatch):
        monkeypatch.setenv("PHONE_ADB_SERIAL", "ENV123")
        client = create_client()
        assert client.serial == "ENV123"
        assert _connect_calls() == []

    def test_device_attached_uses_it_without_connect(self):
        client = create_client(wireless={"enabled": True, "host": "1.2.3.4", "auto_connect": True})
        assert client.serial == "RFCTA0AEKZP"
        assert _connect_calls() == []

    def test_connects_when_no_device_attached(self):
        FakeAdb.start_empty = True
        client = create_client(
            wireless={
                "enabled": True,
                "host": "100.84.31.85",
                "port": 5555,
                "auto_connect": True,
            }
        )
        assert _connect_calls() == ["connect 100.84.31.85:5555"]
        assert client.serial == "100.84.31.85:5555"

    def test_preferred_serial_wins_when_both_attached(self):
        client = create_client(
            wireless={
                "enabled": True,
                "host": "100.84.31.85",
                "auto_connect": True,
                "preferred_serial": "RFCTA0AEKZP",
            }
        )
        # USB device present (fake default); connect must NOT have run,
        # because an authorized device already satisfies resolution.
        assert client.serial == "RFCTA0AEKZP"
        assert _connect_calls() == []

    def test_disabled_wireless_never_connects(self):
        FakeAdb.start_empty = True
        create_client(wireless={"enabled": False, "host": "1.2.3.4", "auto_connect": True})
        assert _connect_calls() == []

    def test_auto_connect_failure_is_tolerated(self, monkeypatch):
        class FailingAdb(FakeAdb):
            def execute(self, *args, **kwargs):
                self.connect_calls.append("connect failed")
                raise OSError("unreachable")

        monkeypatch.setattr(adb_mod, "AdbClient", FailingAdb)
        FakeAdb.start_empty = True
        create_client(
            wireless={"enabled": True, "host": "10.255.255.1", "auto_connect": True}
        )  # must not raise
        assert _connect_calls() == ["connect failed"]

    def test_serial_pinned_when_both_attached_and_no_preference(self, monkeypatch):
        FakeAdb.start_empty = True

        class BothAttached(FakeAdb):
            def list_devices(self):
                if self.connect_calls:  # post-connect state
                    return [
                        {"serial": "RFCTA0AEKZP", "state": "device"},
                        {"serial": "100.84.31.85:5555", "state": "device"},
                    ]
                return []

        monkeypatch.setattr(adb_mod, "AdbClient", BothAttached)
        client = create_client(
            wireless={"enabled": True, "host": "100.84.31.85", "auto_connect": True}
        )
        assert client.serial == "RFCTA0AEKZP"  # first authorized wins without preference
