"""Unit tests for path confinement helpers and their call sites."""

from __future__ import annotations

from pathlib import Path

import pytest

import phone.termux as termux_mod
from phone.logcat import LogcatModule
from phone.paths import PathEscapeError, confined_path
from phone.termux import TermuxClient


class TestConfinedPath:
    def test_accepts_path_inside_root(self, tmp_path):
        target = confined_path(tmp_path, tmp_path / "sub" / "file.txt")
        assert target == (tmp_path / "sub" / "file.txt").resolve()

    def test_accepts_root_itself(self, tmp_path):
        assert confined_path(tmp_path, tmp_path) == tmp_path.resolve()

    def test_accepts_relative_candidate(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert confined_path(tmp_path, "out/file.txt") == (tmp_path / "out" / "file.txt").resolve()

    def test_rejects_dotdot_escape(self, tmp_path):
        with pytest.raises(PathEscapeError):
            confined_path(tmp_path, tmp_path / "sub" / ".." / ".." / "evil.txt")

    def test_rejects_absolute_outside(self, tmp_path):
        with pytest.raises(PathEscapeError):
            confined_path(tmp_path, "C:\\Windows\\system32\\evil.txt")

    def test_rejects_symlink_escape(self, tmp_path):
        # The escape target must live OUTSIDE the root: a junction to a
        # sibling of tmp_path resolves out of it and must be rejected.
        import shutil
        import subprocess
        import tempfile

        real_outside = Path(tempfile.mkdtemp(prefix="paths-escape-"))
        link = tmp_path / "link"
        try:
            try:
                link.symlink_to(real_outside, target_is_directory=True)
            except OSError:
                # Real symlinks need privileges on Windows; a directory
                # junction does not, and Path.resolve() follows it too.
                result = subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(link), str(real_outside)],
                    capture_output=True,
                )
                if result.returncode != 0:
                    pytest.skip("neither symlink nor junction permitted on this system")
            with pytest.raises(PathEscapeError):
                confined_path(tmp_path, link / "x.txt")
        finally:
            shutil.rmtree(real_outside, ignore_errors=True)


def _fake_logcat(*filters, format="threadtime", lines=1000):
    return []


class TestSaveLogsToFile:
    def _module(self, mock_adb_client):
        client = mock_adb_client
        client.logcat = _fake_logcat
        return LogcatModule(client)

    def test_writes_inside_default_base(self, mock_adb_client, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        n = self._module(mock_adb_client).save_logs_to_file("export.log")
        assert n == 0
        assert (tmp_path / "logs" / "export.log").exists()

    def test_rejects_escape_from_base(self, mock_adb_client, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(PathEscapeError):
            self._module(mock_adb_client).save_logs_to_file("../evil.log")

    def test_explicit_base_dir(self, mock_adb_client, tmp_path):
        custom = tmp_path / "custom"
        n = self._module(mock_adb_client).save_logs_to_file("export.log", base_dir=custom)
        assert n == 0
        assert (custom / "export.log").exists()


class TestCreateBootScript:
    def test_rejects_escape(self, monkeypatch, tmp_path):
        monkeypatch.setattr(termux_mod.os.path, "expanduser", lambda p: str(tmp_path / "boot"))
        with pytest.raises(PathEscapeError):
            TermuxClient.create_boot_script("../../evil.sh", "#!/bin/sh")

    def test_accepts_plain_name(self, monkeypatch, tmp_path):
        monkeypatch.setattr(termux_mod.os.path, "expanduser", lambda p: str(tmp_path / "boot"))
        result = TermuxClient.create_boot_script("mytask.sh", "#!/bin/sh\necho hi")
        assert result.startswith(str((tmp_path / "boot").resolve()))
        assert (tmp_path / "boot" / "mytask.sh").exists()
