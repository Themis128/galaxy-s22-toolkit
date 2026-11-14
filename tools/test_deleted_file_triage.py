"""Unit tests for tools/deleted_file_triage.py (hermetic — mock client)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import deleted_file_triage as tri  # noqa: E402


class FakeClient:
    def __init__(self, responses: dict[str, str] | None = None) -> None:
        self.calls: list[tuple[str, ...]] = []
        self._responses = responses or {}

    def execute(self, *args: str) -> str:
        self.calls.append(tuple(args))
        key = " ".join(str(a) for a in args[1:])
        for pattern, out in self._responses.items():
            if pattern in key:
                return out
        return ""


class TestTriageLines:
    def test_counts_and_total(self) -> None:
        lines = tri.triage_lines(
            {"/sdcard/DCIM/.trashed": 3, "/sdcard/Pictures/.trashed": 1},
            512,
        )
        text = "\n".join(lines)
        assert "3 item(s)" in text
        assert "1 item(s)" in text
        assert "TOTAL soft-deleted items: 4" in text
        assert "thumbnails: 512 KB" in text

    def test_thumbnail_na_degrades(self) -> None:
        lines = tri.triage_lines({}, None)
        text = "\n".join(lines)
        assert "thumbnails: N/A" in text
        assert "TOTAL soft-deleted items: 0" in text


class TestScanCommand:
    def test_scan_counts_trashed_items(self, capsys: Any) -> None:
        responses = {
            "/sdcard/DCIM/.trashed": ".trashed-123-a.jpg\n.trashed-456-b.jpg\n",
            "/sdcard/DCIM/.thumbnails": "128 /sdcard/DCIM/.thumbnails\n",
        }
        client = FakeClient(responses)
        rc = tri.cmd_scan(client)
        out = capsys.readouterr().out
        assert rc == 0
        assert "2 item(s)" in out
        assert "thumbnails: 128 KB" in out

    def test_scan_degrades_to_na(self, capsys: Any) -> None:
        client = FakeClient()
        rc = tri.cmd_scan(client)
        out = capsys.readouterr().out
        assert rc == 0
        assert "N/A" in out
        assert "TOTAL soft-deleted items: 0" in out

    def test_scan_never_mutates(self) -> None:
        client = FakeClient()
        tri.cmd_scan(client)
        assert all("rm" not in " ".join(map(str, c)) for c in client.calls)


class TestDeepCommand:
    def test_deep_refuses_unrooted(self, capsys: Any) -> None:
        client = FakeClient({"which": ""})
        rc = tri.cmd_deep(client)
        out = capsys.readouterr().out
        assert rc == 0
        assert "needs root" in out

    def test_deep_root_detected_honest(self, capsys: Any) -> None:
        client = FakeClient({"su": "/system/bin/su\n"})
        rc = tri.cmd_deep(client)
        out = capsys.readouterr().out
        assert rc == 0
        assert "Root detected" in out
        assert "Not implemented on purpose" in out
