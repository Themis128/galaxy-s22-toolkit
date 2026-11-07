"""Unit tests for tools/repair_system.py (hermetic — no device, no flash)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.repair_system import parse_tar_names  # noqa: E402


class TestParseTarNames:
    def test_plain_partitions(self) -> None:
        names = ["boot.img", "vendor_boot.img", "super.img", "meta-data/foo.txt"]
        assert parse_tar_names(names) == ["boot", "vendor_boot", "super"]

    def test_lz4_compressed(self) -> None:
        assert parse_tar_names(["odm.img.lz4"]) == ["odm"]

    def test_ignores_non_partition_files(self) -> None:
        assert parse_tar_names(["README.txt", "firmware.tar.md5"]) == []

    def test_nested_paths(self) -> None:
        assert parse_tar_names(["x/y/boot.img"]) == ["boot"]
