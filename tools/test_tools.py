"""Tests for tools/ utilities (pure logic, no hardware)."""

import stat
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from clean_path_artifacts import ARTIFACT_CHAR, find_artifacts  # noqa: E402
from update_check import verdict_for_age  # noqa: E402


class TestVerdictForAge:
    def test_under_60_is_ok(self):
        assert verdict_for_age(0) == "OK"
        assert verdict_for_age(59) == "OK"

    def test_60_to_90_is_aging(self):
        assert verdict_for_age(60) == "AGING"
        assert verdict_for_age(90) == "AGING"

    def test_over_90_is_outdated(self):
        assert verdict_for_age(91) == "OUTDATED"
        assert verdict_for_age(400) == "OUTDATED"


class TestFindArtifacts:
    def test_finds_mangled_names(self, tmp_path):
        junk = tmp_path / ("C" + ARTIFACT_CHAR + "Userstbaltzakislogcat.py")
        junk.write_text("\n", encoding="utf-8")
        (tmp_path / "normal.py").write_text("x = 1\n", encoding="utf-8")
        found = find_artifacts(tmp_path)
        assert junk in found
        assert len(found) == 1

    def test_ignores_normal_and_git(self, tmp_path):
        (tmp_path / "a.py").write_text("x\n", encoding="utf-8")
        (tmp_path / ".git").mkdir()
        junk = tmp_path / ".git" / ("bad" + ARTIFACT_CHAR + "x.py")
        junk.write_text("x\n", encoding="utf-8")
        assert find_artifacts(tmp_path) == []


class TestFixOnedriveAttrs:
    def test_find_readonly_reports_flagged_file(self, tmp_path):
        import os

        target = tmp_path / "locked.py"
        target.write_text("x\n", encoding="utf-8")
        os.chmod(target, stat.S_IREAD)  # set read-only
        from fix_onedrive_attrs import find_readonly

        try:
            assert find_readonly(tmp_path) == [target]
        finally:
            os.chmod(target, stat.S_IWRITE)

    def test_clear_flags_clears(self, tmp_path):
        import os

        target = tmp_path / "locked.py"
        target.write_text("x\n", encoding="utf-8")
        os.chmod(target, stat.S_IREAD)
        from fix_onedrive_attrs import clear_flags, find_readonly

        cleared = clear_flags([target])
        assert cleared == 1
        assert find_readonly(tmp_path) == []
