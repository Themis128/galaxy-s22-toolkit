"""Tests for tools/ utilities (pure logic, no hardware)."""

import stat
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from clean_path_artifacts import ARTIFACT_CHAR, find_artifacts  # noqa: E402
from dashboard_client import load_api_key  # noqa: E402
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


class TestBackupRetention:
    def _make(self, d, n):
        for i in range(n):
            (d / f"metrics-2026110{i}-120000.db").write_text("x", encoding="utf-8")

    def test_prune_keeps_newest(self, tmp_path):
        from backup_metrics_db import prune_backups

        self._make(tmp_path, 5)
        removed = prune_backups(tmp_path, keep=3)
        assert len(removed) == 2
        assert len(list(tmp_path.glob("metrics-*.db"))) == 3

    def test_prune_keep_all(self, tmp_path):
        from backup_metrics_db import prune_backups

        self._make(tmp_path, 3)
        assert prune_backups(tmp_path, keep=10) == []

    def test_latest_backup(self, tmp_path):
        from backup_metrics_db import latest_backup

        assert latest_backup(tmp_path) is None
        self._make(tmp_path, 2)
        assert latest_backup(tmp_path).name == "metrics-20261101-120000.db"


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


class TestDashboardClient:
    def test_load_api_key_returns_str_or_none(self):
        """With the repo .env present the key parses; without it, None."""
        key = load_api_key()
        assert key is None or (isinstance(key, str) and len(key) > 10)

    def test_repair_requires_confirm(self):
        from dashboard_client import main

        rc = main(["--base-url", "http://127.0.0.1:1", "repair", "clear_app_caches"])
        assert rc == 2
