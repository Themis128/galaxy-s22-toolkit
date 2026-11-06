"""Tests for the retirement tools: system_update UI parsing and
decommission_legacy preflight logic (pure parts, no device/filesystem)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "phone-lib" / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tools.decommission_legacy import Report, is_placeholder  # noqa: E402
from tools.system_update import (  # noqa: E402
    find_tappable,
    parse_bounds,
    summarize_ui,
)

UI_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" content-desc="" bounds="[0,0][1080,2400]">
    <node index="0" text="Settings" content-desc="" clickable="false" bounds="[0,80][1080,200]"/>
    <node index="0" text="Download and install" content-desc="" clickable="true" bounds="[100,1000][980,1100]"/>
    <node index="0" text="Install now" content-desc="" clickable="false" bounds="[100,2000][980,2100]"/>
    <node index="0" text="" content-desc="Download and install. Double-tap to activate." clickable="true" bounds="[100,1200][980,1300]"/>
  </node>
</hierarchy>
"""


class TestSystemUpdateParsing:
    def test_parse_bounds_center(self) -> None:
        assert parse_bounds("[100,1000][980,1100]") == (540, 1050)
        assert parse_bounds("[0,0][0,0]") == (0, 0)

    def test_find_tappable_prefers_clickable(self) -> None:
        # "Install now" node is not clickable -> still returns its center
        center = find_tappable(UI_XML, "Install now")
        assert center == (540, 2050)

    def test_find_tappable_matches_content_desc(self) -> None:
        center = find_tappable(UI_XML, "Download and install")
        # prefers the first CLICKABLE match, not the non-clickable one
        assert center == (540, 1050)

    def test_find_tappable_case_insensitive(self) -> None:
        assert find_tappable(UI_XML, "download AND install") == (540, 1050)

    def test_find_tappable_absent(self) -> None:
        assert find_tappable(UI_XML, "Reboot system") is None

    def test_find_tappable_bad_xml(self) -> None:
        assert find_tappable("<not-xml", "anything") is None

    def test_summarize_ui_lists_labels_with_tap_marker(self) -> None:
        lines = summarize_ui(UI_XML)
        assert "Settings" in lines
        assert "Download and install [tap]" in lines
        assert any("Double-tap" in line for line in lines)

    def test_summarize_ui_bad_xml(self) -> None:
        assert summarize_ui("<broken") == ["<unparseable UI dump>"]


class TestPlaceholderClassification:
    def test_errno22_reparse_point_is_placeholder(self) -> None:
        err = OSError(22, "Invalid argument")
        assert is_placeholder(_raising_path(err)) is True

    def test_winerror362_is_placeholder(self) -> None:
        err = OSError(1, "cloud")
        err.winerror = 362
        assert is_placeholder(_raising_path(err)) is True

    def test_permission_denied_is_not_placeholder(self) -> None:
        err = PermissionError(13, "Access is denied")
        assert is_placeholder(_raising_path(err)) is False

    def test_report_ok_is_all_checks(self) -> None:
        rep = Report()
        rep.add("a", True, "fine")
        rep.add("b", True, "fine")
        assert rep.ok is True
        rep.add("c", False, "bad")
        assert rep.ok is False


def _raising_path(err: OSError) -> Path:
    """A Path whose open() raises ``err`` (patched via subclass)."""

    class RaisingPath(type(Path())):  # type: ignore[misc]
        def open(self, *args: object, **kwargs: object) -> object:
            raise err

    return RaisingPath("dummy")
