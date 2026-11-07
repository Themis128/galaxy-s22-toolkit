"""Unit tests for the WhatsApp viewer filter and fleet parsing (hermetic)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.app import _filter_messages, _parse_adb_devices  # noqa: E402

MESSAGES = [
    {"chat": "Alice", "timestamp": 1700000000, "text": "Hello there"},
    {"chat": "Bob", "timestamp": 1700000100, "text": "General Kenobi"},
    {"chat": "alice.work", "timestamp": 1700000200, "text": "Meeting at 3"},
]


class TestFilterMessages:
    def test_no_filters_returns_all(self) -> None:
        r = _filter_messages(MESSAGES, "", "", 2000)
        assert r["total_in_file"] == 3
        assert r["matches"] == 3

    def test_text_search_case_insensitive(self) -> None:
        r = _filter_messages(MESSAGES, "kenobi", "", 2000)
        assert r["matches"] == 1
        assert r["messages"][0]["chat"] == "Bob"

    def test_chat_filter_case_insensitive(self) -> None:
        r = _filter_messages(MESSAGES, "", "ALICE", 2000)
        assert r["matches"] == 2  # Alice + alice.work

    def test_combined_filters(self) -> None:
        r = _filter_messages(MESSAGES, "meeting", "alice", 2000)
        assert r["matches"] == 1
        assert r["messages"][0]["chat"] == "alice.work"

    def test_limit_caps_messages_not_counts(self) -> None:
        r = _filter_messages(MESSAGES * 10, "", "", 5)
        assert r["matches"] == 30
        assert len(r["messages"]) == 5

    def test_chats_sorted_unique(self) -> None:
        r = _filter_messages(MESSAGES, "", "", 2000)
        assert r["chats"] == ["Alice", "Bob", "alice.work"]


class TestParseAdbDevices:
    def test_wireless_and_usb(self) -> None:
        out = (
            "List of devices attached\n"
            "RFCTA0AEKZP device usb:1-1 product:o2sxxx model:SM_S906B\n"
            "192.168.1.77:5555 device product:o2sxxx model:SM_S906B\n"
        )
        rows = _parse_adb_devices(out)
        assert [r["serial"] for r in rows] == ["RFCTA0AEKZP", "192.168.1.77:5555"]
        assert all(r["state"] == "device" for r in rows)
        assert rows[0]["model"] == "SM_S906B"

    def test_offline_state_kept(self) -> None:
        rows = _parse_adb_devices("List of devices attached\nemulator-5554 offline\n")
        assert rows[0]["state"] == "offline"
        assert rows[0]["model"] == "?"

    def test_header_and_blank_skipped(self) -> None:
        assert _parse_adb_devices("List of devices attached\n\n\n") == []
