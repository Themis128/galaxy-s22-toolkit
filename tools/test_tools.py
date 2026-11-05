"""Tests for tools/ utilities (pure logic, no hardware)."""

from __future__ import annotations

import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.clean_path_artifacts import ARTIFACT_CHAR, find_artifacts  # noqa: E402
from tools.dashboard_client import load_api_key  # noqa: E402
from tools.update_check import verdict_for_age  # noqa: E402


class TestVerdictForAge:
    def test_under_60_is_ok(self) -> None:
        assert verdict_for_age(0) == "OK"
        assert verdict_for_age(59) == "OK"

    def test_60_to_90_is_aging(self) -> None:
        assert verdict_for_age(60) == "AGING"
        assert verdict_for_age(90) == "AGING"

    def test_over_90_is_outdated(self) -> None:
        assert verdict_for_age(91) == "OUTDATED"
        assert verdict_for_age(400) == "OUTDATED"


class TestFindArtifacts:
    def test_finds_mangled_names(self, tmp_path: Path) -> None:
        junk = tmp_path / ("C" + ARTIFACT_CHAR + "Userstbaltzakislogcat.py")
        junk.write_text("\n", encoding="utf-8")
        (tmp_path / "normal.py").write_text("x = 1\n", encoding="utf-8")
        found = find_artifacts(tmp_path)
        assert junk in found
        assert len(found) == 1

    def test_ignores_normal_and_git(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x\n", encoding="utf-8")
        (tmp_path / ".git").mkdir()
        junk = tmp_path / ".git" / ("bad" + ARTIFACT_CHAR + "x.py")
        junk.write_text("x\n", encoding="utf-8")
        assert find_artifacts(tmp_path) == []


class TestBackupRetention:
    def _make(self, d: Path, n: int) -> None:
        for i in range(n):
            (d / f"metrics-2026110{i}-120000.db").write_text("x", encoding="utf-8")

    def test_prune_keeps_newest(self, tmp_path: Path) -> None:
        from tools.backup_metrics_db import prune_backups

        self._make(tmp_path, 5)
        removed = prune_backups(tmp_path, keep=3)
        assert len(removed) == 2
        assert len(list(tmp_path.glob("metrics-*.db"))) == 3

    def test_prune_keep_all(self, tmp_path: Path) -> None:
        from tools.backup_metrics_db import prune_backups

        self._make(tmp_path, 3)
        assert prune_backups(tmp_path, keep=10) == []

    def test_latest_backup(self, tmp_path: Path) -> None:
        from tools.backup_metrics_db import latest_backup

        assert latest_backup(tmp_path) is None
        self._make(tmp_path, 2)
        lb = latest_backup(tmp_path)
        assert lb is not None
        assert lb.name == "metrics-20261101-120000.db"


class TestFixOnedriveAttrs:
    def test_find_readonly_reports_flagged_file(self, tmp_path: Path) -> None:
        import os

        target = tmp_path / "locked.py"
        target.write_text("x\n", encoding="utf-8")
        os.chmod(target, stat.S_IREAD)  # set read-only
        from tools.fix_onedrive_attrs import find_readonly

        try:
            assert find_readonly(tmp_path) == [target]
        finally:
            os.chmod(target, stat.S_IWRITE)

    def test_clear_flags_clears(self, tmp_path: Path) -> None:
        import os

        target = tmp_path / "locked.py"
        target.write_text("x\n", encoding="utf-8")
        os.chmod(target, stat.S_IREAD)
        from tools.fix_onedrive_attrs import clear_flags, find_readonly

        cleared = clear_flags([target])
        assert cleared == 1
        assert find_readonly(tmp_path) == []


class TestDashboardClient:
    def test_load_api_key_returns_str_or_none(self) -> None:
        """With the repo .env present the key parses; without it, None."""
        key = load_api_key()
        assert key is None or (isinstance(key, str) and len(key) > 10)

    def test_repair_requires_confirm(self) -> None:
        from tools.dashboard_client import main

        rc = main(
            ["--allow-private", "--base-url", "http://127.0.0.1:1", "repair", "clear_app_caches"]
        )
        assert rc == 2


class TestRelocateAndPatchAge:
    def test_plan_lists_all_steps(self) -> None:
        from tools.relocate_repo import DEFAULT_TARGET, plan

        steps = plan(DEFAULT_TARGET)
        joined = chr(10).join(steps)
        assert "clone" in joined and "re-task" in joined and "manual" in joined
        assert str(DEFAULT_TARGET) in steps[0]

    def test_under_onedrive_detection(self) -> None:
        from tools.relocate_repo import under_onedrive

        assert under_onedrive(Path("\\Users\\x\\OneDrive\\repo"))
        assert not under_onedrive(Path("\\dev\\repo"))

    def test_patch_age_verdicts(self, tmp_path: Path) -> None:
        import json as _json
        from datetime import date, timedelta

        from tools.insights import security_patch_age

        def write_report(patch_date: str) -> None:
            d = tmp_path / "diagnostics" / "reports"
            d.mkdir(parents=True, exist_ok=True)
            (d / "health_report_2026-11-05.json").write_text(
                _json.dumps({"device": {"security_patch": patch_date}}),
                encoding="utf-8",
            )

        write_report((date.today() - timedelta(days=30)).isoformat())
        assert security_patch_age(tmp_path / "diagnostics" / "reports")["verdict"] == "OK"
        write_report((date.today() - timedelta(days=92)).isoformat())
        assert security_patch_age(tmp_path / "diagnostics" / "reports")["verdict"] == "WATCH"
        write_report((date.today() - timedelta(days=181)).isoformat())
        assert security_patch_age(tmp_path / "diagnostics" / "reports")["verdict"] == "ACT"


class TestAlertEvaluator:
    def test_act_becomes_critical(self) -> None:
        from tools.alerts import evaluate

        item = {"metric": "security patch age", "value": 92, "unit": "days", "verdict": "ACT"}
        alerts = evaluate([item])
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "critical"
        assert alerts[0]["recommendation"]

    def test_watch_becomes_warning(self) -> None:
        from tools.alerts import evaluate

        item = {"metric": "battery drain rate", "value": 14.5, "unit": "%/h", "verdict": "WATCH"}
        assert evaluate([item])[0]["severity"] == "warning"

    def test_ok_and_no_data_are_silent(self) -> None:
        from typing import Any

        from tools.alerts import evaluate

        items: list[dict[str, Any]] = [
            {"metric": "m", "value": 1.0, "verdict": "OK"},
            {"metric": "n", "value": None, "verdict": "NO DATA"},
        ]
        assert evaluate(items) == []
