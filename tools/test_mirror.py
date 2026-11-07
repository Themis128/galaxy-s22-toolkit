"""Unit tests for tools/mirror.py (hermetic — no device, no scrcpy run)."""

from __future__ import annotations

from pathlib import Path

from mirror import build_scrcpy_args, find_scrcpy


class TestBuildScrcpyArgs:
    def test_basic(self):
        args = build_scrcpy_args("RFCTA0AEKZP")
        assert args == ["scrcpy", "-s", "RFCTA0AEKZP", "--max-size", "1280"]

    def test_no_audio_on_failure_not_used(self):
        """scrcpy 5.x removed --no-audio-on-failure; the flag must not return."""
        args = build_scrcpy_args("S1")
        assert "--no-audio-on-failure" not in args
        assert "--no-audio" not in args

    def test_record_adds_no_playback(self):
        args = build_scrcpy_args("S1", record=Path("data/mirrors/x.mp4"))
        assert "--record" in args
        assert "--no-playback" in args

    def test_record_time_limit(self):
        args = build_scrcpy_args("S1", record=Path("x.mp4"), time_limit=30)
        assert "--time-limit" in args
        assert args[args.index("--time-limit") + 1] == "30"

    def test_no_time_limit_without_record(self):
        args = build_scrcpy_args("S1", time_limit=30)
        assert "--time-limit" not in args

    def test_max_size_passthrough(self):
        args = build_scrcpy_args("S1", max_size=1024)
        assert args[args.index("--max-size") + 1] == "1024"


class TestFindScrcpy:
    def test_returns_none_or_str(self):
        result = find_scrcpy()
        assert result is None or isinstance(result, str)
