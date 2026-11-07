"""Unit tests for tools/mirror.py (hermetic — no device, no scrcpy run)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.mirror import build_scrcpy_args, find_scrcpy  # noqa: E402


class TestBuildScrcpyArgs:
    def test_basic(self) -> None:
        args = build_scrcpy_args("RFCTA0AEKZP")
        assert args == ["scrcpy", "-s", "RFCTA0AEKZP", "--max-size", "1280"]

    def test_no_audio_on_failure_not_used(self) -> None:
        """scrcpy 5.x removed --no-audio-on-failure; the flag must not return."""
        args = build_scrcpy_args("S1")
        assert "--no-audio-on-failure" not in args
        assert "--no-audio" not in args

    def test_record_adds_no_playback(self) -> None:
        args = build_scrcpy_args("S1", record=Path("data/mirrors/x.mp4"))
        assert "--record" in args
        assert "--no-playback" in args

    def test_record_time_limit(self) -> None:
        args = build_scrcpy_args("S1", record=Path("x.mp4"), time_limit=30)
        assert "--time-limit" in args
        assert args[args.index("--time-limit") + 1] == "30"

    def test_no_time_limit_without_record(self) -> None:
        args = build_scrcpy_args("S1", time_limit=30)
        assert "--time-limit" not in args

    def test_max_size_passthrough(self) -> None:
        args = build_scrcpy_args("S1", max_size=1024)
        assert args[args.index("--max-size") + 1] == "1024"


class TestFindScrcpy:
    def test_returns_none_or_str(self) -> None:
        result = find_scrcpy()
        assert result is None or isinstance(result, str)
