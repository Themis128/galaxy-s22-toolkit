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


class TestRadioToggleTransportGuard:
    """Radio toggles over wireless ADB kill their own transport: the disable
    succeeds, the connection drops, and the re-enable never arrives — leaving
    the radio off and ADB unreachable. These actions must refuse up front."""

    def _wireless_module(self) -> RepairModule:
        from unittest.mock import MagicMock

        client = MagicMock()
        client.serial = "192.168.1.77:5555"
        return RepairModule(client)

    async def test_reset_wifi_refuses_wireless(self):
        module = self._wireless_module()
        result = await module._repair_reset_wifi()
        assert result.success is False
        assert "USB transport" in result.message
        module.client.execute_async.assert_not_called()

    async def test_reset_mobile_data_refuses_wireless(self):
        module = self._wireless_module()
        result = await module._repair_reset_mobile_data()
        assert result.success is False
        assert "USB transport" in result.message
        module.client.execute_async.assert_not_called()

    async def test_toggle_airplane_mode_refuses_wireless(self):
        module = self._wireless_module()
        result = await module._repair_toggle_airplane_mode()
        assert result.success is False
        assert "USB transport" in result.message
        module.client.execute_async.assert_not_called()

    async def test_flush_dns_refuses_wireless(self):
        module = self._wireless_module()
        result = await module._repair_flush_dns()
        assert result.success is False
        assert "USB transport" in result.message
        module.client.execute_async.assert_not_called()

    async def test_unknown_serial_refuses(self):
        """serial=None is NOT proven USB — the guard must refuse it too.

        Regression: a None serial slipped past the colon check and radio
        toggles ran serial-less against an offline transport, leaving the
        phone's Wi-Fi off (exit 1 on the undeliverable re-enable).
        """
        from unittest.mock import MagicMock

        client = MagicMock()
        client.serial = None
        module = RepairModule(client)
        result = await module._repair_reset_wifi()
        assert result.success is False
        assert "identity is unknown" in result.message
        module.client.execute_async.assert_not_called()

    async def test_radio_toggles_still_run_over_usb(self, repair):
        """USB serial (no colon) bypasses the guard — commands are issued."""
        result = await repair._repair_reset_wifi()
        assert result.success is True
        assert repair.client.execute_async.call_count >= 2


class TestBloatwareGenerationFilter:
    """One-UI-generation-aware bloatware target selection (multi-Galaxy Phase 2)."""

    @staticmethod
    def _client_with_oneui(mock_adb_client, raw: str) -> None:
        """Make `shell getprop ro.build.version.oneui` return `raw`."""
        base = mock_adb_client.execute.side_effect

        def side_effect(*args, **kwargs):
            if args[:3] == ("shell", "getprop", "ro.build.version.oneui"):
                return raw
            # RepairModule issues pm list as a single shell string
            if args[:2] == ("shell", "pm list packages -d"):
                return "package:com.bloatware.app\n"
            if args[:2] == ("shell", "pm list packages"):
                return (
                    "package:com.android.systemui\n"
                    "package:com.example.app\n"
                    "package:com.samsung.android.app.spage\n"
                )
            return base(*args, **kwargs)

        mock_adb_client.execute.side_effect = side_effect
        mock_adb_client.execute_async.side_effect = side_effect

    def test_bloatware_for_one_ui_matrix(self):
        """Generation math: entries from lower generations stay applicable."""
        flat = RepairModule.SAMSUNG_BLOATWARE
        by_gen = RepairModule.SAMSUNG_BLOATWARE_BY_GEN
        assert RepairModule.bloatware_for_one_ui(None) == flat
        assert RepairModule.bloatware_for_one_ui(1) == by_gen[1]
        assert RepairModule.bloatware_for_one_ui(2) == by_gen[1] + by_gen[2]
        assert RepairModule.bloatware_for_one_ui(4) == by_gen[1] + by_gen[2] + by_gen[4]
        assert RepairModule.bloatware_for_one_ui(6) == flat

    def test_one_ui_major_from_prop(self):
        """OOSSPP integer and dotted One-UI props both parse; junk -> None."""
        f = RepairModule._one_ui_major_from_prop
        assert f("60100") == 6
        assert f("50100") == 5
        assert f("20000") == 2
        assert f("6.0") == 6
        assert f("5.1") == 5
        assert f("600") is None  # too short to be an OOSSPP code
        assert f("unknown") is None
        assert f("") is None
        assert f("  60100  ") == 6

    async def test_gen6_targets_all_generations(self, mock_adb_client):
        """One UI 6: every generation group is a candidate target."""
        self._client_with_oneui(mock_adb_client, "60100")
        module = RepairModule(mock_adb_client)
        result = await module._repair_disable_bloatware()
        assert result.success is True
        details = result.details
        # Only the gen-1 spage entry exists in the conftest package list
        assert details["disabled"] == ["com.samsung.android.app.spage"]
        assert details["filtered_by_generation"] == []
        assert len(details["absent_on_model"]) == len(RepairModule.SAMSUNG_BLOATWARE) - 1

    async def test_gen2_filters_gen4_entry(self, mock_adb_client):
        """One UI 2: the One-UI-4 entry is filtered before any pm call."""
        self._client_with_oneui(mock_adb_client, "20000")
        module = RepairModule(mock_adb_client)
        result = await module._repair_disable_bloatware()
        details = result.details
        assert details["filtered_by_generation"] == ["com.samsung.android.app.routines"]
        disable_calls = [
            c.args[1]
            for c in mock_adb_client.execute_async.call_args_list
            if len(c.args) >= 2 and "disable-user" in str(c.args[1])
        ]
        # spage (gen 1, installed) attempted; routines (gen 4) never called
        assert any("spage" in call for call in disable_calls)
        assert not any("routines" in call for call in disable_calls)

    async def test_unknown_generation_targets_everything(self, mock_adb_client):
        """No oneui prop -> conservative flat list; absent filter still applies."""
        self._client_with_oneui(mock_adb_client, "")
        module = RepairModule(mock_adb_client)
        result = await module._repair_disable_bloatware()
        assert result.details["filtered_by_generation"] == []
        assert result.details["disabled"] == ["com.samsung.android.app.spage"]
