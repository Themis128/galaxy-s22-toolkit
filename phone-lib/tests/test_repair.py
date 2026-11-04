"""Unit tests for the repair module (approval flow + history persistence)."""

from __future__ import annotations

import json

import pytest

from phone.repair import RepairAction, RepairModule


@pytest.fixture
def repair(mock_adb_client) -> RepairModule:
    return RepairModule(mock_adb_client)


class TestPendingActions:
    async def test_no_diagnostics_returns_auto_approve(self, repair):
        actions = await repair.get_pending_actions(None)
        assert actions
        assert all(a.auto_approve for a in actions)

    async def test_storage_issue_recommends_storage_actions(self, repair):
        results = [{"name": "storage", "status": "warning", "message": "disk almost full"}]
        actions = await repair.get_pending_actions(results)
        names = {a.name for a in actions}
        assert "clear_app_caches" in names
        assert "remove_temp_files" in names


class TestApproval:
    async def test_confirm_callback_decides(self, mock_adb_client):
        seen = []

        async def cb(action: RepairAction) -> bool:
            seen.append(action.name)
            return True

        module = RepairModule(mock_adb_client, confirm_callback=cb)
        action = RepairAction("a", "d", "storage", "low")
        assert await module.request_approval(action) is True
        assert seen == ["a"]

    async def test_without_callback_uses_auto_approve_flag(self, repair):
        low = RepairAction("low-action", "d", "storage", "low", auto_approve=True)
        gated = RepairAction("gated", "d", "storage", "medium", auto_approve=False)
        assert await repair.request_approval(low) is True
        assert await repair.request_approval(gated) is False


class TestHistoryPersistence:
    async def test_execute_persists_to_jsonl(self, mock_adb_client, tmp_path):
        history_file = tmp_path / "repair_history.jsonl"
        module = RepairModule(mock_adb_client, history_path=history_file)
        result = await module.execute_action("clear_app_caches")

        assert history_file.exists()
        lines = history_file.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["action"]["name"] == "clear_app_caches"
        assert data["success"] == result.success

    async def test_history_roundtrip(self, mock_adb_client, tmp_path):
        history_file = tmp_path / "repair_history.jsonl"
        m1 = RepairModule(mock_adb_client, history_path=history_file)
        await m1.execute_action("clear_app_caches")
        assert len(m1.history) == 1

        m2 = RepairModule(mock_adb_client, history_path=history_file)
        assert len(m2.history) == 1
        assert m2.history[0].action.name == "clear_app_caches"

    async def test_history_trimming(self, mock_adb_client, tmp_path):
        history_file = tmp_path / "repair_history.jsonl"
        module = RepairModule(mock_adb_client, history_path=history_file, history_max_entries=3)
        for _ in range(5):
            await module.execute_action("clear_app_caches")
        assert len(module.history) == 3
        lines = history_file.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 3
        assert json.loads(lines[0])["message"] != ""

    async def test_corrupt_history_file_tolerated(self, mock_adb_client, tmp_path):
        history_file = tmp_path / "repair_history.jsonl"
        history_file.write_text("not json\n{bad json\n", encoding="utf-8")
        module = RepairModule(mock_adb_client, history_path=history_file)
        assert module.history == []
