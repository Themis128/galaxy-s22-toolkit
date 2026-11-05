#!/usr/bin/env python3
"""Interactive CLI Diagnostics with Approve/Repair Flow.

Runs diagnostics, presents issues, and allows user to approve/run repair actions.
"""

# ruff: noqa: T201  # Interactive CLI requires print statements

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

# Add phone-lib to path (must be before imports)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "phone-lib" / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from diagnostics.run_diagnostics import DiagnosticsRunner  # noqa: E402
from phone import create_client  # noqa: E402
from phone.notify import DesktopNotifier  # noqa: E402
from phone.repair import RepairAction, RepairModule, RepairResult  # noqa: E402


def _load_yaml_config(config_path: Path) -> dict[str, Any]:
    """Load the diagnostics config for repair/notification settings."""
    try:
        import yaml

        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


class InteractiveRepairCLI:
    """Interactive CLI for diagnostics and repair."""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config = _load_yaml_config(config_path)
        self.client: Any = None  # AdbClient; set in initialize()
        self.repair_module: RepairModule | None = None
        self.notifier: DesktopNotifier | None = None
        self.diagnostics_results: list[dict[str, Any]] = []
        self.pending_actions: list[RepairAction] = []
        # Repair policy (config.yaml -> repair:), with safe defaults
        repair_cfg = self.config.get("repair", {})
        self.auto_approve_risk_levels = set(repair_cfg.get("auto_approve_risk_levels", ["low"]))
        self.approval_timeout_s = int(repair_cfg.get("approval_timeout_s", 120))
        self.desktop_notifications = bool(repair_cfg.get("desktop_notifications", True))
        self.history_path = repair_cfg.get("history_file")
        if self.history_path:
            self.history_path = str(PROJECT_ROOT / self.history_path)

    async def initialize(self) -> bool:
        """Initialize ADB client and repair module."""
        try:
            device_cfg = self.config.get("device") or {}
            wireless = device_cfg.get("wireless_adb") or None
            if wireless:
                wireless = {**wireless, "preferred_serial": device_cfg.get("serial")}
            self.client = create_client(wireless=wireless)
            if not self.client.is_connected:
                print(
                    "❌ No ADB device connected. Please connect your device and enable USB debugging."
                )
                return False

            device_info = self.client.device.get_device_info()
            print(
                f"✅ Connected to {device_info.model} (Android {device_info.android_version}, API {device_info.api_level})"
            )

            # Desktop toast notifications (optional; console fallback below)
            if self.desktop_notifications:
                # Deep-link must match the dashboard's actual port
                dash_port = os.getenv("DASHBOARD_PORT", "8081")
                self.notifier = DesktopNotifier(
                    app_id="Galaxy Toolkit",
                    dashboard_url=f"http://127.0.0.1:{dash_port}",
                )

            # Create repair module with interactive confirmation callback and
            # persistent history
            self.repair_module = RepairModule(
                self.client,
                confirm_callback=self._confirm_action,
                history_path=self.history_path,
            )
            return True
        except Exception as e:
            print(f"❌ Failed to initialize: {e}")
            return False

    async def _confirm_action(self, action: RepairAction) -> bool:
        """Approval policy: config risk levels, then toast, then console."""
        if action.risk_level in self.auto_approve_risk_levels or action.auto_approve:
            print(f"✅ {action.name} auto-approved (risk: {action.risk_level})")
            return True

        # Desktop toast with Approve/Deny buttons
        if self.notifier:
            try:
                approved = await self.notifier.request_approval_async(
                    f"Repair: {action.name}",
                    f"{action.description}\nRisk: {action.risk_level.upper()}",
                    timeout_s=self.approval_timeout_s,
                )
                print(
                    f"{'✅' if approved else '🚫'} {action.name} {'approved' if approved else 'denied'} via desktop notification"
                )
                return approved
            except Exception:
                pass  # fall back to console prompt

        print(f"\n{'=' * 60}")
        print(f"🔧 Repair Action: {action.name}")
        print(f"   Description: {action.description}")
        print(
            f"   Category: {action.category} | Risk: {action.risk_level.upper()} | Est. Duration: {action.estimated_duration_s}s"
        )
        print(f"{'=' * 60}")

        while True:
            response = input("Approve this action? [y/N/a=approve all/q=quit]: ").strip().lower()
            if response in ("y", "yes"):
                return True
            elif response in ("n", "no", ""):
                return False
            elif response in ("a", "all"):
                # Approve all remaining pending actions
                for a in self.pending_actions:
                    a.auto_approve = True
                return True
            elif response in ("q", "quit"):
                print("🛑 Quitting...")
                sys.exit(0)
            else:
                print("Please enter y, n, a, or q")

    async def run_diagnostics(self) -> list[dict[str, Any]]:
        """Run diagnostics and return results."""
        print("\n📊 Running diagnostics...")
        runner = DiagnosticsRunner(self.config_path)
        exit_code = await runner.run_async()
        self.diagnostics_results = [asdict(r) for r in runner.results]

        # Print summary
        passed = sum(1 for r in self.diagnostics_results if r.get("status") == "pass")
        warnings = sum(1 for r in self.diagnostics_results if r.get("status") == "warning")
        failed = sum(1 for r in self.diagnostics_results if r.get("status") in ("fail", "error"))

        print(
            f"\n📈 Diagnostics Complete: {passed} passed, {warnings} warnings, {failed} failed (exit code: {exit_code})"
        )

        # Show issues
        issues = [
            r for r in self.diagnostics_results if r.get("status") in ("warning", "fail", "error")
        ]
        if issues:
            print("\n⚠️  Issues Found:")
            for i, issue in enumerate(issues, 1):
                status_emoji = "❌" if issue.get("status") in ("fail", "error") else "⚠️"
                print(
                    f"  {i}. {status_emoji} {issue.get('name', 'Unknown')}: {issue.get('message', 'No details')}"
                )
        else:
            print("\n✅ No issues found!")

        return self.diagnostics_results

    async def get_recommended_actions(self) -> list[RepairAction]:
        """Get recommended repair actions based on diagnostics."""
        if not self.repair_module:
            return []

        self.pending_actions = await self.repair_module.get_pending_actions(
            self.diagnostics_results
        )
        return self.pending_actions

    def display_actions(self, actions: list[RepairAction]) -> None:
        """Display available repair actions."""
        if not actions:
            print("\n✅ No repair actions recommended.")
            return

        print(f"\n🔧 Recommended Repair Actions ({len(actions)}):")
        print("-" * 80)

        for i, action in enumerate(actions, 1):
            risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(action.risk_level, "⚪")
            auto_badge = " [AUTO]" if action.auto_approve else ""
            root_badge = " [ROOT]" if action.requires_root else ""

            print(f"  {i:2d}. {risk_emoji} {action.name}{auto_badge}{root_badge}")
            print(f"      {action.description}")
            print(
                f"      Category: {action.category} | Risk: {action.risk_level.upper()} | Est: {action.estimated_duration_s}s"
            )

        print("-" * 80)

    async def run_selected_actions(
        self, actions: list[RepairAction], indices: list[int]
    ) -> list[RepairResult]:
        """Run selected repair actions."""
        selected = [actions[i - 1] for i in indices if 1 <= i <= len(actions)]
        if not selected:
            print("No valid actions selected.")
            return []
        if not self.repair_module:
            print("Repair module not initialized.")
            return []

        print(f"\n🚀 Executing {len(selected)} repair action(s)...\n")

        action_names = [a.name for a in selected]
        results = await self.repair_module.execute_multiple(action_names)

        # Display results
        print("\n📋 Repair Results:")
        print("=" * 80)
        for result in results:
            status_emoji = "✅" if result.success else "❌"
            print(f"  {status_emoji} {result.action.name}: {result.message}")
            if result.details:
                for key, value in result.details.items():
                    print(f"      {key}: {value}")
            print(f"      Duration: {result.duration_ms:.0f}ms")
            if result.requires_reboot:
                print("      ⚠️  REBOOT REQUIRED")

        successful = sum(1 for r in results if r.success)
        print(f"\n📊 Summary: {successful}/{len(results)} successful")

        # Desktop toast with the batch summary
        if self.notifier:
            failed = len(results) - successful
            title = "Repair complete" if not failed else f"Repair: {failed} failed"
            self.notifier.notify(
                title,
                f"{successful}/{len(results)} repair actions succeeded",
                long=bool(failed),
            )

        return results

    async def run_interactive(self) -> None:
        """Main interactive loop."""
        print("=" * 80)
        print("📱 Galaxy Interactive Diagnostics & Repair")
        print("=" * 80)

        # Initialize
        if not await self.initialize():
            return

        # Run diagnostics
        await self.run_diagnostics()

        # Get recommended actions
        actions = await self.get_recommended_actions()
        self.display_actions(actions)

        if not actions:
            print("\n🎉 No repairs needed!")
            return

        # Interactive selection
        while True:
            print("\nOptions:")
            print("  [1-N]  Run specific action by number")
            print("  [a]    Run ALL recommended actions")
            print("  [c]    Run only AUTO-APPROVE actions")
            print("  [r]    Re-run diagnostics")
            print("  [h]    Show repair history")
            print("  [q]    Quit")

            choice = input("\nSelect option: ").strip().lower()

            if choice == "q":
                print("👋 Goodbye!")
                break
            elif choice == "r":
                await self.run_diagnostics()
                actions = await self.get_recommended_actions()
                self.display_actions(actions)
            elif choice == "h":
                self.show_history()
            elif choice == "a":
                await self.run_selected_actions(actions, list(range(1, len(actions) + 1)))
            elif choice == "c":
                auto_actions = [a for a in actions if a.auto_approve]
                if auto_actions:
                    indices = [actions.index(a) + 1 for a in auto_actions]
                    await self.run_selected_actions(actions, indices)
                else:
                    print("No auto-approve actions available.")
            elif choice.isdigit():
                idx = int(choice)
                if 1 <= idx <= len(actions):
                    await self.run_selected_actions(actions, [idx])
                else:
                    print(f"Invalid selection. Choose 1-{len(actions)}")
            else:
                print("Invalid option. Please try again.")

    def show_history(self) -> None:
        """Show repair history."""
        if not self.repair_module or not self.repair_module.history:
            print("\n📜 No repair history yet.")
            return

        print("\n📜 Repair History:")
        print("=" * 80)
        for result in self.repair_module.history:
            status_emoji = "✅" if result.success else "❌"
            timestamp = result.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            print(f"  {status_emoji} [{timestamp}] {result.action.name}: {result.message}")
            if result.duration_ms:
                print(f"      Duration: {result.duration_ms:.0f}ms")
        print("=" * 80)


async def main() -> None:
    config_path = PROJECT_ROOT / "diagnostics" / "config.yaml"
    cli = InteractiveRepairCLI(config_path)
    await cli.run_interactive()


if __name__ == "__main__":
    asyncio.run(main())
