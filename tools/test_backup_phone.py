"""Unit tests for tools/backup_phone.py (hermetic — manifest decision logic)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.backup_phone import needs_pull  # noqa: E402


class TestNeedsPull:
    ENTRY = {
        "rel": "DCIM/photo.jpg",
        "remote": "/sdcard/DCIM/photo.jpg",
        "size": 100,
        "mtime": "2026-11-07 10:00",
    }

    def test_new_file_pulled(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("tools.backup_phone.MIRROR", tmp_path)
        assert needs_pull(self.ENTRY, {}, full=False) is True

    def test_unchanged_skipped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("tools.backup_phone.MIRROR", tmp_path)
        (tmp_path / "DCIM").mkdir()
        (tmp_path / "DCIM" / "photo.jpg").write_bytes(b"x" * 100)
        manifest = {"DCIM/photo.jpg": {"size": 100, "mtime": "2026-11-07 10:00"}}
        assert needs_pull(self.ENTRY, manifest, full=False) is False

    def test_size_change_pulled(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("tools.backup_phone.MIRROR", tmp_path)
        (tmp_path / "DCIM").mkdir()
        (tmp_path / "DCIM" / "photo.jpg").write_bytes(b"x" * 100)
        manifest = {"DCIM/photo.jpg": {"size": 50, "mtime": "2026-11-07 10:00"}}
        assert needs_pull(self.ENTRY, manifest, full=False) is True

    def test_mtime_change_pulled(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("tools.backup_phone.MIRROR", tmp_path)
        (tmp_path / "DCIM").mkdir()
        (tmp_path / "DCIM" / "photo.jpg").write_bytes(b"x" * 100)
        manifest = {"DCIM/photo.jpg": {"size": 100, "mtime": "2026-11-01 09:00"}}
        assert needs_pull(self.ENTRY, manifest, full=False) is True

    def test_missing_local_pulled_even_if_manifest_current(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("tools.backup_phone.MIRROR", tmp_path)
        manifest = {"DCIM/photo.jpg": {"size": 100, "mtime": "2026-11-07 10:00"}}
        assert needs_pull(self.ENTRY, manifest, full=False) is True

    def test_full_always_pulls(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("tools.backup_phone.MIRROR", tmp_path)
        (tmp_path / "DCIM").mkdir()
        (tmp_path / "DCIM" / "photo.jpg").write_bytes(b"x" * 100)
        manifest = {"DCIM/photo.jpg": {"size": 100, "mtime": "2026-11-07 10:00"}}
        assert needs_pull(self.ENTRY, manifest, full=True) is True
