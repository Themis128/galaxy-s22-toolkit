"""Unit tests for tools/media_repair.py (hermetic — tmp trees, no device)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import media_repair as mr  # noqa: E402

FTYP = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2avc1mp41"
MOOV = b"\x00\x00\x00\x6bmoov" + b"\x00" * 100
MDAT = b"\x00\x00\x30\x00mdat" + b"\x00" * 200


def _w(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


class TestMp4Verdict:
    def test_intact_has_ftyp_and_moov(self) -> None:
        data = FTYP + MDAT + MOOV
        assert mr.mp4_verdict(data, data[-1024:]) == "intact"

    def test_truncated_has_ftyp_no_moov(self) -> None:
        data = FTYP + MDAT
        assert mr.mp4_verdict(data, b"") == "truncated"

    def test_garbage_is_unknown(self) -> None:
        assert mr.mp4_verdict(b"not a video at all", b"") == "unknown"


class TestJpegVerdict:
    def test_intact_soi_eoi(self) -> None:
        assert mr.jpeg_verdict(b"\xff\xd8\xff\xe0body", b"tail\xff\xd9") == "intact"

    def test_intact_with_trailing_metadata(self) -> None:
        """Samsung JPEGs carry metadata after EOI — intact, not truncated."""
        assert mr.jpeg_verdict(b"\xff\xd8body", b"\xff\xd9\x00tail-metadata") == "intact"

    def test_truncated_missing_eoi(self) -> None:
        assert mr.jpeg_verdict(b"\xff\xd8\xff\xe0body", b"tail\x00\x00") == "truncated"

    def test_not_jpeg_is_unknown(self) -> None:
        assert mr.jpeg_verdict(b"PNG\x89", b"") == "unknown"


class TestScanDir:
    def test_groups_by_verdict(self, tmp_path: Path) -> None:
        _w(tmp_path / "a.mp4", FTYP + MDAT + MOOV)
        _w(tmp_path / "b.mp4", FTYP + MDAT)
        _w(tmp_path / "c.jpg", b"\xff\xd8body\xff\xd9")
        _w(tmp_path / "d.txt", b"hello")
        grouped = mr.scan_dir(tmp_path)
        assert len(grouped["intact"]) == 2
        assert len(grouped["truncated"]) == 1
        assert len(grouped["unknown"]) == 1

    def test_missing_dir_empty_groups(self, tmp_path: Path) -> None:
        grouped = mr.scan_dir(tmp_path / "nope")
        assert grouped == {"intact": [], "truncated": [], "unknown": []}


class TestRepairFile:
    def test_no_tool_outcome(self, tmp_path: Path, monkeypatch: Any) -> None:
        broken = _w(tmp_path / "b.mp4", FTYP + MDAT)
        monkeypatch.setattr(mr, "_find_untrunc", lambda: None)
        monkeypatch.setattr(mr, "_find_ffmpeg", lambda: None)
        out = mr.repair_file(broken, None)
        assert out["outcome"] == "no-tool"
        assert not (tmp_path / "b.fixed.mp4").exists()
        assert broken.read_bytes() == FTYP + MDAT  # original untouched

    def test_untrunc_success_writes_new_file(self, tmp_path: Path, monkeypatch: Any) -> None:
        import subprocess

        broken = _w(tmp_path / "b.mp4", FTYP + MDAT)
        ref = _w(tmp_path / "ref.mp4", FTYP + MDAT + MOOV)
        monkeypatch.setattr(mr, "_find_untrunc", lambda: "fake-untrunc")
        monkeypatch.setattr(mr, "_find_ffmpeg", lambda: None)

        def fake_run(cmd: list[str], **kwargs: object) -> object:
            assert cmd[0] == "fake-untrunc"
            Path(cmd[2]).with_name("b.fixed.mp4").write_bytes(FTYP + MOOV)
            return subprocess.CompletedProcess(cmd, 0, b"", b"")

        monkeypatch.setattr("subprocess.run", fake_run)
        out = mr.repair_file(broken, ref)
        assert out["outcome"] == "repaired-untrunc"
        assert (tmp_path / "b.fixed.mp4").exists()

    def test_remux_fallback_when_no_untrunc(self, tmp_path: Path, monkeypatch: Any) -> None:
        import subprocess

        broken = _w(tmp_path / "b.mp4", FTYP + MDAT)
        monkeypatch.setattr(mr, "_find_untrunc", lambda: None)
        monkeypatch.setattr(mr, "_find_ffmpeg", lambda: "fake-ffmpeg")

        def fake_run(cmd: list[str], **kwargs: object) -> object:
            Path(cmd[-1]).write_bytes(FTYP + MOOV)
            return subprocess.CompletedProcess(cmd, 0, b"", b"")

        monkeypatch.setattr("subprocess.run", fake_run)
        out = mr.repair_file(broken, None)
        assert out["outcome"] == "repaired-remux"
        assert (tmp_path / "b.fixed.mp4").exists()
