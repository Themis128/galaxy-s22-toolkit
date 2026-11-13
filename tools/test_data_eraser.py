"""Unit tests for tools/data_eraser.py (hermetic — no device, no adb)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import data_eraser  # noqa: E402


class FakeClient:
    """Minimal ADB client stand-in keyed on command shape."""

    def __init__(self, responses: dict[tuple[str, ...], str] | None = None) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.serial = "FAKE000SERIAL"
        self._responses = responses or {}

    def execute(self, *args: str) -> str:
        self.calls.append(tuple(args))
        for keys, out in self._responses.items():
            match = True
            for i, key in enumerate(keys):
                if i >= len(args) or (key != "*" and args[i] != key):
                    match = False
                    break
            if match and len(args) >= len(keys):
                return out
        return ""


DF_FRAGMENT = (
    "Filesystem      Size  Used Avail Use% Mounted on\n"
    "/dev/fuse       114G   96G   18G  84% /storage/emulated\n"
    "tmpfs            11G  3.4M   11G   1% /dev\n"
)


class TestParseDf:
    def test_df_h_fragment(self) -> None:
        assert data_eraser.parse_df(DF_FRAGMENT) == (96.0, 18.0)

    def test_dumpsys_row(self) -> None:
        row = "/dev/block/dm-8 114G 96G 18G 84% /data\n"
        assert data_eraser.parse_df(row) == (96.0, 18.0)

    def test_garbage_returns_none(self) -> None:
        assert data_eraser.parse_df("no mounts here\n") is None

    def test_empty_returns_none(self) -> None:
        assert data_eraser.parse_df("") is None


class TestParseAppCount:
    def test_counts_package_lines(self) -> None:
        out = "package:com.a\npackage:com.b\npackage:com.c\n"
        assert data_eraser.parse_app_count(out) == 3

    def test_empty_returns_none(self) -> None:
        assert data_eraser.parse_app_count("") is None
        assert data_eraser.parse_app_count("error: no packages\n") is None


class TestBuildCertificate:
    def test_shape(self) -> None:
        actions = [
            {
                "action": "free-space",
                "timestamp": "2026-11-13T00:00:00",
                "outcome": "ok",
            }
        ]
        cert = data_eraser.build_certificate({"model": "SM-S906B"}, actions)
        assert set(cert) == {"device", "actions", "honesty_note", "generated"}
        assert cert["actions"][0]["action"] == "free-space"
        assert "FBE" in cert["honesty_note"]


class TestConfirmTyped:
    def test_exact_match(self) -> None:
        assert data_eraser.confirm_typed("p: ", "ERASE-PHONE", input_fn=lambda _p: "ERASE-PHONE")

    def test_wrong_then_right(self) -> None:
        answers = iter(["nope", "ERASE-PHONE"])
        assert data_eraser.confirm_typed("p: ", "ERASE-PHONE", input_fn=lambda _p: next(answers))

    def test_wrong_twice(self) -> None:
        answers = iter(["nope", "nope"])
        assert not data_eraser.confirm_typed(
            "p: ", "ERASE-PHONE", input_fn=lambda _p: next(answers)
        )

    def test_eof_returns_false(self) -> None:
        def eof(_p: str) -> str:
            raise EOFError()

        assert not data_eraser.confirm_typed("p: ", "ERASE-PHONE", input_fn=eof)

    def test_empty_returns_false(self) -> None:
        assert not data_eraser.confirm_typed("p: ", "ERASE-PHONE", input_fn=lambda _p: "")


class TestCliGates:
    def test_free_space_requires_yes(self) -> None:
        client = FakeClient()
        rc = data_eraser.main(["free-space"])
        assert rc != 0
        assert client.calls == []  # client never constructed before the gate

    def test_reset_guidance_no_execute(self, capsys: Any) -> None:
        rc = data_eraser.main(["reset", "--serial", "FAKE000SERIAL"])
        assert rc == 0
        assert "No reset performed" in capsys.readouterr().out
