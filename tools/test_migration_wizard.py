"""Unit tests for tools/migration_wizard.py (hermetic — mock client)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import migration_wizard as mw  # noqa: E402


class FakeClient:
    def __init__(self, responses: dict[str, str] | None = None) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.pulled: list[tuple[str, str]] = []
        self.pushed: list[tuple[str, str]] = []
        self._responses: dict[str, str] = responses or {}

    def execute(self, *args: str) -> str:
        self.calls.append(tuple(args))
        key = " ".join(str(a) for a in args[1:])
        for pattern, out in self._responses.items():
            if pattern in key:
                return str(out)
        return ""

    def list_devices(self) -> list[dict[str, str]]:
        return self._devices

    _devices: list[dict[str, str]] = []

    def pull(self, remote: str, local: str) -> str:
        self.pulled.append((remote, local))
        return local

    def push(self, local: str, remote: str) -> str:
        self.pushed.append((local, remote))
        return remote


class TestStagingDir:
    def test_deterministic_path(self) -> None:
        d = mw.staging_dir("20261114-120000")
        assert d == mw.STAGING / "20261114-120000"
        assert "migration" in str(d)


class TestResolveSerial:
    def test_single_device_auto_selects(self) -> None:
        client = FakeClient()
        client._devices = [{"serial": "S1", "state": "device"}]
        assert mw._resolve_serial(client, None) == "S1"

    def test_multiple_devices_refuse_without_serial(self) -> None:
        client = FakeClient()
        client._devices = [
            {"serial": "S1", "state": "device"},
            {"serial": "S2", "state": "device"},
        ]
        try:
            mw._resolve_serial(client, None)
            raise AssertionError("expected SystemExit")
        except SystemExit as exc:
            assert "--serial" in str(exc)

    def test_explicit_serial_passes_through(self) -> None:
        client = FakeClient()
        client._devices = [
            {"serial": "S1", "state": "device"},
            {"serial": "S2", "state": "device"},
        ]
        assert mw._resolve_serial(client, "S2") == "S2"

    def test_no_devices_returns_none(self) -> None:
        client = FakeClient()
        client._devices = []
        assert mw._resolve_serial(client, None) is None


class TestRemoteWalk:
    def test_lists_paths(self) -> None:
        client = FakeClient(
            {"/sdcard/Ringtones": "/sdcard/Ringtones/a.mp3\n/sdcard/Ringtones/b.mp3\n"}
        )
        files = mw._remote_walk(client, "/sdcard/Ringtones")
        assert files == [
            ("/sdcard/Ringtones/a.mp3", 0),
            ("/sdcard/Ringtones/b.mp3", 0),
        ]

    def test_absent_root_returns_empty(self) -> None:
        client = FakeClient()

        def boom(*args: str) -> str:
            raise RuntimeError("offline")

        client.execute = boom  # type: ignore[method-assign]
        assert mw._remote_walk(client, "/sdcard/DCIM") == []


class TestExportImport:
    def test_export_dry_run_no_pulls(self, tmp_path: Path, capsys: Any) -> None:
        client = FakeClient({"/sdcard/Ringtones": "/sdcard/Ringtones/a.mp3\n"})
        mw.STAGING = tmp_path
        rc = mw._cmd_export(client, "20261114-120000", yes=False, serial="S1")
        out = capsys.readouterr().out
        assert rc == 0
        assert "Dry run" in out
        assert client.pulled == []
        assert "Ringtones/a.mp3" in out

    def test_export_with_yes_pulls_into_staging(self, tmp_path: Path) -> None:
        client = FakeClient({"/sdcard/Ringtones": "/sdcard/Ringtones/a.mp3\n"})
        mw.STAGING = tmp_path
        rc = mw._cmd_export(client, "20261114-120000", yes=True, serial="S1")
        assert rc == 0
        assert client.pulled == [
            ("/sdcard/Ringtones/a.mp3", str(tmp_path / "20261114-120000" / "Ringtones" / "a.mp3"))
        ]

    def test_import_never_overwrites(self, tmp_path: Path) -> None:
        client = FakeClient({"/sdcard": "Y"})
        staged = tmp_path / "20261114-120000" / "Ringtones"
        staged.mkdir(parents=True)
        (staged / "a.mp3").write_bytes(b"x")
        mw.STAGING = tmp_path
        rc = mw._cmd_import(client, "20261114-120000", yes=True, overwrite=False)
        assert rc == 0
        assert client.pushed == []  # remote exists -> skipped

    def test_import_pushes_when_remote_missing(self, tmp_path: Path) -> None:
        client = FakeClient({"/sdcard": "N"})
        staged = tmp_path / "20261114-120000" / "Ringtones"
        staged.mkdir(parents=True)
        (staged / "a.mp3").write_bytes(b"x")
        mw.STAGING = tmp_path
        rc = mw._cmd_import(client, "20261114-120000", yes=True, overwrite=False)
        assert rc == 0
        assert len(client.pushed) == 1

    def test_import_missing_staging_fails(self, tmp_path: Path, capsys: Any) -> None:
        mw.STAGING = tmp_path
        rc = mw._cmd_import(FakeClient(), "missing-ts", yes=True, overwrite=False)
        out = capsys.readouterr().out
        assert rc == 1
        assert "run export first" in out


class TestPlanCommand:
    def test_plan_is_read_only_checklist(self, capsys: Any) -> None:
        client = FakeClient()
        rc = mw._cmd_plan(client)
        out = capsys.readouterr().out
        assert rc == 0
        assert "/sdcard/DCIM" in out
        assert "Authenticator seeds" in out
        assert "Google account sync" in out
