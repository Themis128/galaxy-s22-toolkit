"""Unit tests for tools/selective_restore.py (hermetic — tmp mirror, no device)."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import selective_restore as sr  # noqa: E402
from tools.selective_restore import MirrorFile  # noqa: E402


def _mk(path: Path, size: int, mtime: float | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    if mtime is not None:
        import os

        os.utime(path, (mtime, mtime))


class TestIterMirrorFiles:
    def test_walks_and_rels_are_posix(self, tmp_path: Path) -> None:
        _mk(tmp_path / "DCIM" / "Camera" / "a.jpg", 10)
        _mk(tmp_path / "Pictures" / "b.png", 20)
        _mk(tmp_path / "ignore.txt", 1)
        files = sr.iter_mirror_files(tmp_path)
        rels = [f.rel for f in files]
        assert set(rels) == {"DCIM/Camera/a.jpg", "Pictures/b.png", "ignore.txt"}
        assert all(Path(f.local).is_file() for f in files)

    def test_missing_mirror_returns_empty(self, tmp_path: Path) -> None:
        assert sr.iter_mirror_files(tmp_path / "nope") == []

    def test_empty_dirs_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "DCIM").mkdir()
        assert sr.iter_mirror_files(tmp_path) == []


class TestFilterFiles:
    def _files(self) -> list[MirrorFile]:
        return [
            MirrorFile(rel="DCIM/a.jpg", local="x", size=1, mtime=1700000000.0),
            MirrorFile(rel="DCIM/b.txt", local="x", size=2, mtime=1700000100.0),
            MirrorFile(rel="Pictures/c.jpg", local="x", size=3, mtime=1700000200.0),
        ]

    def test_roots_filter(self) -> None:
        files = self._files()
        out = sr.filter_files(files, roots=["DCIM"])
        assert [f.rel for f in out] == ["DCIM/a.jpg", "DCIM/b.txt"]

    def test_pattern_filter(self) -> None:
        out = sr.filter_files(self._files(), pattern="*.jpg")
        assert [f.rel for f in out] == ["DCIM/a.jpg", "Pictures/c.jpg"]

    def test_newer_than_filter(self) -> None:
        # tz-agnostic: derive the cutoff from the fixture's own mtimes
        cutoff = datetime.fromtimestamp(1700000150)
        out = sr.filter_files(self._files(), newer_than=cutoff)
        assert [f.rel for f in out] == ["Pictures/c.jpg"]

    def test_filters_combine_with_and(self) -> None:
        cutoff = datetime(2023, 11, 15)
        out = sr.filter_files(self._files(), roots=["DCIM"], pattern="*.txt", newer_than=cutoff)
        assert [f.rel for f in out] == ["DCIM/b.txt"]

    def test_no_match(self) -> None:
        assert sr.filter_files(self._files(), roots=["Movies"]) == []


class TestPlanRestore:
    def test_partitions_by_remote_existence(self) -> None:
        files = [
            MirrorFile(rel="DCIM/a.jpg", local="x", size=1, mtime=0.0),
            MirrorFile(rel="DCIM/b.jpg", local="x", size=1, mtime=0.0),
        ]
        to_push, skipped = sr.plan_restore(files, remote_exists={"DCIM/b.jpg"})
        assert [f.rel for f in to_push] == ["DCIM/a.jpg"]
        assert skipped == ["DCIM/b.jpg"]

    def test_no_conflicts_all_push(self) -> None:
        files = [MirrorFile(rel="DCIM/a.jpg", local="x", size=1, mtime=0.0)]
        to_push, skipped = sr.plan_restore(files, remote_exists=set())
        assert [f.rel for f in to_push] == ["DCIM/a.jpg"]
        assert skipped == []


class TestCliGates:
    def test_restore_dry_run_default_no_device(self, tmp_path: Path, capsys: Any) -> None:
        """Without --yes the CLI prints the plan and never touches a device."""
        _mk(tmp_path / "DCIM" / "a.jpg", 10)
        rc = sr.main(["restore", "--mirror", str(tmp_path)])
        out = capsys.readouterr().out
        assert rc == 0
        assert "Dry run" in out
        assert "push DCIM/a.jpg" in out

    def test_restore_zero_matches_exits_zero(self, tmp_path: Path, capsys: Any) -> None:
        _mk(tmp_path / "DCIM" / "a.jpg", 10)
        rc = sr.main(["restore", "--mirror", str(tmp_path), "--roots", "Movies"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "nothing to restore" in out

    def test_list_on_missing_mirror(self, capsys: Any) -> None:
        rc = sr.main(["list", "--mirror", str(Path("/nonexistent-mirror"))])
        out = capsys.readouterr().out
        assert rc == 0
        assert "nothing to restore" in out
