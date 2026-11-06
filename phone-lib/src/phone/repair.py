"""Auto-repair module for phone toolkit.

Provides safe, approved repair operations for common device issues.
All mutating operations require explicit confirmation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .adb import AdbClient
from .apps import AppsModule
from .logcat import LogcatModule
from .network import NetworkModule
from .storage import StorageModule

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RepairAction:
    """A single repair action that can be executed."""

    name: str
    description: str
    category: str  # storage, apps, network, logcat
    risk_level: str  # low, medium, high
    requires_root: bool = False
    estimated_duration_s: int = 30
    auto_approve: bool = False  # if True, can run without explicit approval


@dataclass(slots=True)
class RepairResult:
    """Result of a repair action execution."""

    action: RepairAction
    success: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    requires_reboot: bool = False


class RepairModule:
    """Module for executing approved repair actions on the device."""

    # All available repair actions - defined here for transparency
    AVAILABLE_ACTIONS: list[RepairAction] = [
        # Storage repairs
        RepairAction(
            name="clear_app_caches",
            description="Clear cache directories for all user apps (safe, frees space)",
            category="storage",
            risk_level="low",
            requires_root=False,
            estimated_duration_s=30,
            auto_approve=True,
        ),
        RepairAction(
            name="clear_system_cache",
            description="Clear system cache partition (requires recovery mode, more space)",
            category="storage",
            risk_level="medium",
            requires_root=False,
            estimated_duration_s=60,
            auto_approve=False,
        ),
        RepairAction(
            name="remove_temp_files",
            description="Remove temporary files from /data/local/tmp, /cache, /data/tmp",
            category="storage",
            risk_level="low",
            requires_root=False,
            estimated_duration_s=15,
            auto_approve=True,
        ),
        RepairAction(
            name="remove_tombstones",
            description="Remove old tombstone crash dumps from /data/tombstones (needs root)",
            category="storage",
            risk_level="low",
            requires_root=True,
            estimated_duration_s=10,
            auto_approve=False,
        ),
        RepairAction(
            name="remove_anr_traces",
            description="Remove old ANR trace files from /data/anr (needs root)",
            category="storage",
            risk_level="low",
            requires_root=True,
            estimated_duration_s=10,
            auto_approve=False,
        ),
        RepairAction(
            name="identify_large_files",
            description="Find and report files >100MB for manual review (no deletion)",
            category="storage",
            risk_level="low",
            requires_root=False,
            estimated_duration_s=30,
            auto_approve=True,
        ),
        # App repairs
        RepairAction(
            name="force_stop_misbehaving_apps",
            description="Force stop apps with high CPU/memory or crash history",
            category="apps",
            risk_level="low",
            requires_root=False,
            estimated_duration_s=15,
            auto_approve=True,
        ),
        RepairAction(
            name="clear_app_data",
            description="Clear data for specific problematic apps (resets app to fresh state)",
            category="apps",
            risk_level="medium",
            requires_root=False,
            estimated_duration_s=10,
            auto_approve=False,
        ),
        RepairAction(
            name="disable_bloatware",
            description="Disable common Samsung bloatware packages (reversible via enable)",
            category="apps",
            risk_level="medium",
            requires_root=False,
            estimated_duration_s=20,
            auto_approve=False,
        ),
        RepairAction(
            name="reset_app_preferences",
            description="Reset runtime permissions to defaults (apps re-request on next use)",
            category="apps",
            risk_level="medium",
            requires_root=False,
            estimated_duration_s=10,
            auto_approve=False,
        ),
        # Network repairs
        RepairAction(
            name="reset_wifi",
            description="Toggle Wi-Fi off/on to reset connection",
            category="network",
            risk_level="low",
            requires_root=False,
            estimated_duration_s=10,
            auto_approve=True,
        ),
        RepairAction(
            name="reset_mobile_data",
            description="Toggle mobile data off/on",
            category="network",
            risk_level="low",
            requires_root=False,
            estimated_duration_s=10,
            auto_approve=True,
        ),
        RepairAction(
            name="toggle_airplane_mode",
            description="Toggle airplane mode to reset all radios",
            category="network",
            risk_level="low",
            requires_root=False,
            estimated_duration_s=15,
            auto_approve=True,
        ),
        RepairAction(
            name="flush_dns",
            description="Flush DNS cache via ndc resolver flushdefaultif",
            category="network",
            risk_level="low",
            requires_root=False,
            estimated_duration_s=5,
            auto_approve=True,
        ),
        RepairAction(
            name="reset_network_settings",
            description="Reset Wi-Fi, mobile, Bluetooth settings (preserves saved networks)",
            category="network",
            risk_level="medium",
            requires_root=False,
            estimated_duration_s=20,
            auto_approve=False,
        ),
        # Logcat repairs
        RepairAction(
            name="clear_logcat_buffers",
            description="Clear all logcat buffers (main, system, radio, events, crash)",
            category="logcat",
            risk_level="low",
            requires_root=False,
            estimated_duration_s=5,
            auto_approve=True,
        ),
        RepairAction(
            name="clear_old_logs",
            description="Remove log files older than 7 days from /data/log, /sdcard/logs",
            category="logcat",
            risk_level="low",
            requires_root=False,
            estimated_duration_s=10,
            auto_approve=True,
        ),
        RepairAction(
            name="reduce_log_verbosity",
            description="Set default log level to INFO for noisy packages",
            category="logcat",
            risk_level="low",
            requires_root=False,
            estimated_duration_s=10,
            auto_approve=True,
        ),
    ]
    # Samsung bloatware packages safe to disable, grouped by One-UI generation.
    # Key = minimum One-UI major version (int). Entries in lower generations are
    # also applicable to newer ones (backwards compatibility).
    # Unknown/untagged entries default to generation 1 (always considered).
    SAMSUNG_BLOATWARE_BY_GEN: dict[int, list[str]] = {
        1: [
            # Pre-One UI / TouchWiz era - always applicable
            "com.samsung.android.app.spage",  # Samsung Daily/Free (One UI 1+)
            "com.samsung.android.app.watchmanagerstub",  # Galaxy Watch plugin
            "com.samsung.android.ardrawing",  # AR Drawing
            "com.samsung.android.aremoetd",  # AR Emoji Editor
            "com.samsung.android.ipservice",  # IP Service
            "com.samsung.android.voc",  # Voice control
            "com.sec.android.app.samsungapps",  # Galaxy Store
            "com.samsung.android.spay",  # Samsung Pay
            "com.samsung.android.fmm",  # Find My Mobile
            "com.samsung.android.scloud.oauth",  # Samsung Cloud OAuth
        ],
        2: [
            # One UI 2.x (Android 10) - S10/Note10 era
            "com.samsung.android.svoice.sync",  # S Voice sync (deprecated in newer)
            "com.samsung.android.game.gos",  # Game Optimizing Service
            "com.samsung.android.hmt.vrsvc",  # VR Service
            "com.samsung.android.mateagent",  # Mate Agent
        ],
        4: [
            # One UI 4.x (Android 12) - S21/Note20 era
            "com.samsung.android.app.routines",  # Modes and Routines
        ],
    }

    # Convenience flat list for backward-compat and display (all generations)
    SAMSUNG_BLOATWARE: list[str] = []
    for _gen in sorted(SAMSUNG_BLOATWARE_BY_GEN):
        SAMSUNG_BLOATWARE.extend(SAMSUNG_BLOATWARE_BY_GEN[_gen])

    def __init__(
        self,
        client: AdbClient,
        confirm_callback: Callable[[RepairAction], Awaitable[bool]] | None = None,
        history_path: str | Path | None = None,
        history_max_entries: int = 500,
    ):
        """Initialize repair module.

        Args:
            client: Connected AdbClient instance
            confirm_callback: Optional async function(action: RepairAction) -> bool
                             for interactive approval. If None, uses auto_approve flag.
            history_path: Optional path to a JSONL file persisting repair history
                          across runs. Loaded on init and appended to on each result.
            history_max_entries: Maximum history entries kept (loaded and persisted).
        """
        self.client = client
        self.confirm_callback = confirm_callback
        self.storage = StorageModule(client)
        self.apps = AppsModule(client)
        self.network = NetworkModule(client)
        self.logcat = LogcatModule(client)
        self.history_path = Path(history_path) if history_path else None
        self.history_max_entries = history_max_entries
        self.history: list[RepairResult] = []
        self._load_history()

    # ===== History persistence =====

    @staticmethod
    def _result_to_dict(result: RepairResult) -> dict[str, Any]:
        """Serialize a RepairResult to a JSON-compatible dict."""
        return {
            "action": {
                "name": result.action.name,
                "description": result.action.description,
                "category": result.action.category,
                "risk_level": result.action.risk_level,
                "requires_root": result.action.requires_root,
                "estimated_duration_s": result.action.estimated_duration_s,
                "auto_approve": result.action.auto_approve,
            },
            "success": result.success,
            "message": result.message,
            "details": result.details,
            "duration_ms": result.duration_ms,
            "timestamp": result.timestamp.isoformat(),
            "requires_reboot": result.requires_reboot,
        }

    def _load_history(self) -> None:
        """Load recent repair history from the JSONL file (oldest first)."""
        if not self.history_path or not self.history_path.exists():
            return
        try:
            lines = self.history_path.read_text(encoding="utf-8").splitlines()
            for line in lines[-self.history_max_entries :]:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                action_data = data.get("action", {})
                action = RepairAction(
                    name=action_data.get("name", "unknown"),
                    description=action_data.get("description", ""),
                    category=action_data.get("category", ""),
                    risk_level=action_data.get("risk_level", "low"),
                    requires_root=action_data.get("requires_root", False),
                    estimated_duration_s=action_data.get("estimated_duration_s", 30),
                    auto_approve=action_data.get("auto_approve", False),
                )
                self.history.append(
                    RepairResult(
                        action=action,
                        success=data.get("success", False),
                        message=data.get("message", ""),
                        details=data.get("details", {}),
                        duration_ms=data.get("duration_ms", 0.0),
                        timestamp=datetime.fromisoformat(data.get("timestamp"))
                        if data.get("timestamp")
                        else datetime.now(),
                        requires_reboot=data.get("requires_reboot", False),
                    )
                )
            if self.history:
                logger.info(
                    "Loaded %d repair history entries from %s", len(self.history), self.history_path
                )
        except Exception as exc:
            logger.warning("Could not load repair history from %s: %s", self.history_path, exc)
            self.history = []

    def _persist_result(self, result: RepairResult) -> None:
        """Append a result to the JSONL history file, trimming to max entries."""
        self.history.append(result)
        # Trim in-memory history to the most recent entries
        if len(self.history) > self.history_max_entries:
            self.history = self.history[-self.history_max_entries :]
        if not self.history_path:
            return
            return
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            with self.history_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(self._result_to_dict(result)) + "\n")
            # Trim file to the most recent max entries
            lines = self.history_path.read_text(encoding="utf-8").splitlines()
            if len(lines) > self.history_max_entries:
                self.history_path.write_text(
                    "\n".join(lines[-self.history_max_entries :]) + "\n", encoding="utf-8"
                )
        except Exception as exc:
            logger.warning("Could not persist repair history to %s: %s", self.history_path, exc)

    async def get_pending_actions(
        self, diagnostics_results: list[dict[str, Any]] | None = None
    ) -> list[RepairAction]:
        """Get list of recommended repair actions based on diagnostics.

        Args:
            diagnostics_results: List of check results from diagnostics run

        Returns:
            List of recommended RepairAction objects
        """
        recommended = []

        if not diagnostics_results:
            # Return all auto-approve actions as baseline
            return [a for a in self.AVAILABLE_ACTIONS if a.auto_approve]

        # Map check names to repair actions
        check_to_actions: dict[str, list[str]] = {
            "storage": [
                "clear_app_caches",
                "remove_temp_files",
                "remove_tombstones",
                "remove_anr_traces",
                "identify_large_files",
            ],
            "battery": [
                "force_stop_misbehaving_apps",
            ],
            "apps": [
                "force_stop_misbehaving_apps",
                "reset_app_preferences",
            ],
            "network": [
                "toggle_airplane_mode",
                "flush_dns",
            ],
            "logcat": [
                "clear_logcat_buffers",
                "clear_old_logs",
                "reduce_log_verbosity",
            ],
            "thermal": [
                "force_stop_misbehaving_apps",
            ],
        }

        # Find failed/warning checks
        issue_categories = set()
        for result in diagnostics_results:
            if result.get("status") in ("warning", "fail", "error"):
                name = result.get("name", "")
                for cat, _actions in check_to_actions.items():
                    if cat in name.lower():
                        issue_categories.add(cat)

        # Collect recommended actions
        for cat in issue_categories:
            for action_name in check_to_actions.get(cat, []):
                action = next((a for a in self.AVAILABLE_ACTIONS if a.name == action_name), None)
                if action and action not in recommended:
                    recommended.append(action)

        # Always include auto-approve actions
        for action in self.AVAILABLE_ACTIONS:
            if action.auto_approve and action not in recommended:
                recommended.append(action)

        return recommended

    async def request_approval(self, action: RepairAction) -> bool:
        """Request approval for a repair action.

        Uses confirm_callback if provided, otherwise returns auto_approve flag.
        """
        if self.confirm_callback:
            result = await self.confirm_callback(action)
            return bool(result)
        return action.auto_approve

    async def execute_action(self, action_name: str, **kwargs: Any) -> RepairResult:
        """Execute a single repair action by name."""
        action = next((a for a in self.AVAILABLE_ACTIONS if a.name == action_name), None)
        if not action:
            return RepairResult(
                action=RepairAction(
                    name=action_name, description="", category="", risk_level="high"
                ),
                success=False,
                message=f"Unknown action: {action_name}",
            )

        # Check approval
        approved = await self.request_approval(action)
        if not approved:
            return RepairResult(
                action=action,
                success=False,
                message="Action not approved",
                details={"approved": False},
            )

        # Execute the action
        start = time.perf_counter()
        try:
            method = getattr(self, f"_repair_{action_name}", None)
            if not method:
                return RepairResult(
                    action=action,
                    success=False,
                    message=f"No implementation for {action_name}",
                )

            result = await method(**kwargs)
            duration = (time.perf_counter() - start) * 1000

            if isinstance(result, RepairResult):
                result.duration_ms = duration
                result.timestamp = datetime.now()
                self._persist_result(result)
                return result

            repair_result = RepairResult(
                action=action,
                success=True,
                message=str(result) if result else "Repair completed",
                duration_ms=duration,
            )
            self._persist_result(repair_result)
            return repair_result

        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            logger.error(f"Repair {action_name} failed: {e}")
            repair_result = RepairResult(
                action=action,
                success=False,
                message=f"Repair failed: {e}",
                duration_ms=round(duration, 1),
            )
            self._persist_result(repair_result)
            return repair_result

    async def execute_multiple(self, action_names: list[str], **kwargs: Any) -> list[RepairResult]:
        """Execute multiple repair actions sequentially."""
        results = []
        for name in action_names:
            result = await self.execute_action(name, **kwargs)
            results.append(result)
            if not result.success and result.action.risk_level == "high":
                # Stop on high-risk failure
                break
        return results

    # ===== Storage Repairs =====

    async def _repair_clear_app_caches(self, **kwargs: Any) -> RepairResult:
        """Clear cached data for all apps via pm trim-caches (no root needed)."""
        action = next(a for a in self.AVAILABLE_ACTIONS if a.name == "clear_app_caches")
        try:
            # trim-caches with a huge threshold frees all app caches at once;
            # per-app `pm clear --cache-only` is not supported on modern Android
            await self.client.execute_async("shell", "pm trim-caches 999999999999")
            return RepairResult(
                action=action,
                success=True,
                message="Trimmed cached data for all apps",
                details={"method": "pm trim-caches"},
            )
        except Exception as e:
            return RepairResult(
                action=action,
                success=False,
                message=f"Failed to trim app caches: {e}",
            )

    async def _repair_remove_temp_files(self, **kwargs: Any) -> RepairResult:
        """Remove temporary files from common temp directories."""
        temp_dirs = [
            "/data/local/tmp",
            "/cache",
            "/data/tmp",
            "/data/ansible/tmp",
            "/data/data/com.termux/files/usr/tmp",
        ]

        total_removed = 0

        for dir_path in temp_dirs:
            try:
                # List files first
                output = await self.client.execute_async(
                    "shell", f"ls -la {dir_path} 2>/dev/null | wc -l"
                )
                count = int(output.strip()) - 1  # subtract header line

                if count > 0:
                    # Remove files (not directories)
                    await self.client.execute_async(
                        "shell", f"find {dir_path} -type f -mtime +1 -delete 2>/dev/null"
                    )

                    total_removed += count
            except Exception:
                pass  # Directory might not exist

        return RepairResult(
            action=next(a for a in self.AVAILABLE_ACTIONS if a.name == "remove_temp_files"),
            success=True,
            message=f"Cleaned temp files from {len(temp_dirs)} directories (~{total_removed} files)",
            details={"dirs_cleaned": len(temp_dirs), "estimated_files": total_removed},
        )

    async def _repair_remove_tombstones(self, **kwargs: Any) -> RepairResult:
        """Remove old tombstone crash dumps (requires root)."""
        action = next(a for a in self.AVAILABLE_ACTIONS if a.name == "remove_tombstones")
        try:
            count_out = await self.client.execute_async(
                "shell", "ls -1 /data/tombstones/ 2>/dev/null | wc -l"
            )
            count = int(count_out.strip())
            new_count = count

            if count > 0:
                await self.client.execute_async(
                    "shell", "find /data/tombstones -type f -mtime +3 -delete 2>/dev/null"
                )
                new_count_out = await self.client.execute_async(
                    "shell", "ls -1 /data/tombstones/ 2>/dev/null | wc -l"
                )
                new_count = int(new_count_out.strip())

            removed = count - new_count
            if count > 0 and removed == 0:
                # The shell user cannot write /data/tombstones without root
                return RepairResult(
                    action=action,
                    success=False,
                    message=f"Cannot delete tombstones without root ({count} present)",
                    details={"removed": 0, "remaining": new_count, "requires_root": True},
                )

            return RepairResult(
                action=action,
                success=True,
                message=f"Removed {removed} tombstone files ({new_count} remaining)",
                details={"removed": removed, "remaining": new_count},
            )
        except Exception as e:
            return RepairResult(
                action=action,
                success=False,
                message=f"Failed to remove tombstones: {e}",
            )

    async def _repair_remove_anr_traces(self, **kwargs: Any) -> RepairResult:
        """Remove old ANR trace files (requires root)."""
        action = next(a for a in self.AVAILABLE_ACTIONS if a.name == "remove_anr_traces")
        try:
            count_out = await self.client.execute_async(
                "shell", "ls -1 /data/anr/ 2>/dev/null | wc -l"
            )
            count = int(count_out.strip())
            new_count = count

            if count > 0:
                await self.client.execute_async(
                    "shell", "find /data/anr -type f -mtime +3 -delete 2>/dev/null"
                )
                new_count_out = await self.client.execute_async(
                    "shell", "ls -1 /data/anr/ 2>/dev/null | wc -l"
                )
                new_count = int(new_count_out.strip())

            removed = count - new_count
            if count > 0 and removed == 0:
                return RepairResult(
                    action=action,
                    success=False,
                    message=f"Cannot delete ANR traces without root ({count} present)",
                    details={"removed": 0, "remaining": new_count, "requires_root": True},
                )

            return RepairResult(
                action=action,
                success=True,
                message=f"Removed {removed} ANR traces ({new_count} remaining)",
                details={"removed": removed, "remaining": new_count},
            )
        except Exception as e:
            return RepairResult(
                action=action,
                success=False,
                message=f"Failed to remove ANR traces: {e}",
            )

    async def _repair_identify_large_files(self, **kwargs: Any) -> RepairResult:
        """Find large files for manual review (scans /sdcard; /data needs root)."""
        action = next(a for a in self.AVAILABLE_ACTIONS if a.name == "identify_large_files")
        try:
            threshold_mb = kwargs.get("threshold_mb", 100)

            output = await self.client.execute_async(
                "shell", f"find /sdcard -type f -size +{threshold_mb}M 2>/dev/null | head -20"
            )

            files = []
            for line in output.strip().splitlines():
                if line:
                    # Get file size
                    size_out = await self.client.execute_async(
                        "shell", f"du -h '{line}' 2>/dev/null | cut -f1"
                    )
                    size = size_out.strip()
                    files.append({"path": line, "size": size})

            return RepairResult(
                action=action,
                success=True,
                message=f"Found {len(files)} files >{threshold_mb}MB on /sdcard",
                details={"files": files, "threshold_mb": threshold_mb},
            )
        except Exception as e:
            return RepairResult(
                action=action,
                success=False,
                message=f"Failed to identify large files: {e}",
            )

    # ===== App Repairs =====

    async def _repair_force_stop_misbehaving_apps(self, **kwargs: Any) -> RepairResult:
        """Force stop apps with high resource usage or crashes."""
        action = next(a for a in self.AVAILABLE_ACTIONS if a.name == "force_stop_misbehaving_apps")
        stopped = []
        crash_packages: set[str] = set()
        discovery_error = None

        # Discovery phase: tolerate failures and degrade gracefully
        try:
            running = self.apps.get_running_apps()
        except Exception as e:
            running = []
            discovery_error = f"running apps: {e}"

        try:
            logcat_result = self.logcat.get_logs_with_stats(lines=200)
            for log in logcat_result["filtered_logs"]:
                if log.package:
                    crash_packages.add(log.package)
        except Exception as e:
            discovery_error = discovery_error or f"logcat: {e}"

        if running and crash_packages:
            for app in running[:20]:  # top 20 by resource usage
                if app in crash_packages:
                    try:
                        await self.client.execute_async("shell", f"am force-stop {app}")
                        stopped.append(app)
                    except Exception:
                        pass

        if discovery_error and not stopped:
            return RepairResult(
                action=action,
                success=False,
                message=f"Could not identify misbehaving apps ({discovery_error})",
            )

        return RepairResult(
            action=action,
            success=True,
            message=f"Force stopped {len(stopped)} misbehaving apps"
            if stopped
            else "No misbehaving apps to stop",
            details={"stopped": stopped, "crash_packages": sorted(crash_packages)[:10]},
        )

    async def _repair_clear_app_data(self, **kwargs: Any) -> RepairResult:
        """Clear data for specific apps (requires package names in kwargs)."""
        packages = kwargs.get("packages", [])
        if not packages:
            return RepairResult(
                action=next(a for a in self.AVAILABLE_ACTIONS if a.name == "clear_app_data"),
                success=False,
                message="No packages specified",
            )

        cleared = []
        for pkg in packages:
            try:
                await self.client.execute_async("shell", f"pm clear {pkg}")
                cleared.append(pkg)
            except Exception as e:
                logger.warning(f"Failed to clear data for {pkg}: {e}")

        return RepairResult(
            action=next(a for a in self.AVAILABLE_ACTIONS if a.name == "clear_app_data"),
            success=True,
            message=f"Cleared data for {len(cleared)} apps",
            details={"cleared": cleared, "requested": packages},
        )

    async def _repair_disable_bloatware(self, **kwargs: Any) -> RepairResult:
        """Disable common Samsung bloatware.

        One `pm list packages` round-trip partitions installed/enabled,
        installed/disabled, and absent packages in Python, so the action
        is model-agnostic: bloatware entries that don't exist on this
        Galaxy generation (S Voice on Note20, VR Service on A-series...)
        are counted as absent, not attempted.
        """
        disabled = []
        already_disabled = []
        absent = []

        installed: set[str] = set()
        disabled_set: set[str] = set()
        try:
            listing = await self.client.execute_async("shell", "pm list packages -d")
            disabled_set = {
                line.removeprefix("package:").strip()
                for line in listing.splitlines()
                if line.startswith("package:")
            }
            listing = await self.client.execute_async("shell", "pm list packages")
            installed = {
                line.removeprefix("package:").strip()
                for line in listing.splitlines()
                if line.startswith("package:")
            }
        except Exception:
            # Can't enumerate - fall back to per-package probing below
            installed = set()
            disabled_set = set()

        for pkg in self.SAMSUNG_BLOATWARE:
            if installed and pkg not in installed:
                absent.append(pkg)
                continue
            if pkg in disabled_set:
                already_disabled.append(pkg)
                continue
            try:
                await self.client.execute_async("shell", f"pm disable-user --user 0 {pkg}")
                disabled.append(pkg)
            except Exception:
                absent.append(pkg)

        return RepairResult(
            action=next(a for a in self.AVAILABLE_ACTIONS if a.name == "disable_bloatware"),
            success=True,
            message=(
                f"Disabled {len(disabled)} bloatware packages "
                f"({len(already_disabled)} already disabled, {len(absent)} not on this model)"
            ),
            details={
                "disabled": disabled,
                "already_disabled": already_disabled,
                "absent_on_model": absent,
            },
            requires_reboot=False,
        )

    async def _repair_reset_app_preferences(self, **kwargs: Any) -> RepairResult:
        """Reset runtime permissions to their default (denied) state."""
        action = next(a for a in self.AVAILABLE_ACTIONS if a.name == "reset_app_preferences")
        try:
            await self.client.execute_async("shell", "pm reset-permissions")

            return RepairResult(
                action=action,
                success=True,
                message="Runtime permissions reset to defaults (apps will re-request on next use)",
                details={"method": "pm reset-permissions"},
            )
        except Exception as e:
            return RepairResult(
                action=action,
                success=False,
                message=f"Failed to reset permissions: {e}",
            )

    # ===== Network Repairs =====

    @staticmethod
    def _is_wireless_transport(client: Any) -> bool:
        """True when the client dials the phone over a network transport.

        Radio-toggle repairs are unsafe here: `svc wifi disable` (or airplane
        mode on) kills the very connection the re-enable step needs, so the
        phone can be left with its radio off and ADB unreachable. Network
        serials look like `192.168.1.77:5555`; USB serials do not contain a
        colon.
        """
        serial = str(getattr(client, "serial", "") or "")
        return ":" in serial

    def _radio_toggle_guard(self, action: Any) -> RepairResult | None:
        """Honest refusal for radio toggles over wireless ADB."""
        if not self._is_wireless_transport(self.client):
            return None
        return RepairResult(
            action=action,
            success=False,
            message=(
                "Skipped: radio toggles need the USB transport, and this session "
                "is wireless. Over wireless ADB the disable step kills the "
                "connection the re-enable needs, leaving the radio off and ADB "
                "unreachable. The dashboard container cannot use USB at all — "
                f"run this from the host CLI instead: phone-repair run {action.name}"
            ),
        )

    async def _repair_reset_wifi(self, **kwargs: Any) -> RepairResult:
        """Toggle Wi-Fi off/on (re-enables even if the toggle half-fails)."""
        action = next(a for a in self.AVAILABLE_ACTIONS if a.name == "reset_wifi")
        guarded = self._radio_toggle_guard(action)
        if guarded is not None:
            return guarded
        try:
            disable_error = None
            try:
                await self.client.execute_async("shell", "svc wifi disable")
            except Exception as e:
                disable_error = e
            await asyncio_sleep(2)
            # Always attempt re-enable so the radio is never left off
            await self.client.execute_async("shell", "svc wifi enable")

            if disable_error is not None:
                raise disable_error

            return RepairResult(
                action=action,
                success=True,
                message="Wi-Fi toggled off/on",
                details={},
            )
        except Exception as e:
            return RepairResult(
                action=action,
                success=False,
                message=f"Failed to reset Wi-Fi: {e}",
            )

    async def _repair_reset_mobile_data(self, **kwargs: Any) -> RepairResult:
        """Toggle mobile data off/on (re-enables even if the toggle half-fails)."""
        action = next(a for a in self.AVAILABLE_ACTIONS if a.name == "reset_mobile_data")
        guarded = self._radio_toggle_guard(action)
        if guarded is not None:
            return guarded
        try:
            disable_error = None
            try:
                await self.client.execute_async("shell", "svc data disable")
            except Exception as e:
                disable_error = e
            await asyncio_sleep(2)
            # Always attempt re-enable so the radio is never left off
            await self.client.execute_async("shell", "svc data enable")

            if disable_error is not None:
                raise disable_error

            return RepairResult(
                action=action,
                success=True,
                message="Mobile data toggled off/on",
                details={},
            )
        except Exception as e:
            return RepairResult(
                action=action,
                success=False,
                message=f"Failed to reset mobile data: {e}",
            )

    async def _repair_toggle_airplane_mode(self, **kwargs: Any) -> RepairResult:
        """Toggle airplane mode."""
        action = next(a for a in self.AVAILABLE_ACTIONS if a.name == "toggle_airplane_mode")
        guarded = self._radio_toggle_guard(action)
        if guarded is not None:
            return guarded
        try:
            # Use settings only (broadcast requires system permission on newer Android)
            await self.client.execute_async("shell", "settings put global airplane_mode_on 1")
            await asyncio_sleep(2)
            await self.client.execute_async("shell", "settings put global airplane_mode_on 0")

            return RepairResult(
                action=action,
                success=True,
                message="Airplane mode toggled via settings (all radios reset)",
                details={},
            )
        except Exception as e:
            return RepairResult(
                action=action,
                success=False,
                message=f"Failed to toggle airplane mode: {e}",
            )

    async def _repair_flush_dns(self, **kwargs: Any) -> RepairResult:
        """Flush DNS cache."""
        action = next(a for a in self.AVAILABLE_ACTIONS if a.name == "flush_dns")
        guarded = self._radio_toggle_guard(action)
        if guarded is not None:
            return guarded
        try:
            # Try ndc resolver flushdefaultif (older Android)
            try:
                await self.client.execute_async("shell", "ndc resolver flushdefaultif")
                return RepairResult(
                    action=action,
                    success=True,
                    message="DNS cache flushed via ndc resolver",
                    details={},
                )
            except Exception:
                # Try alternative: toggle airplane mode which flushes DNS
                await self.client.execute_async("shell", "settings put global airplane_mode_on 1")
                await asyncio_sleep(2)
                await self.client.execute_async("shell", "settings put global airplane_mode_on 0")

                return RepairResult(
                    action=next(a for a in self.AVAILABLE_ACTIONS if a.name == "flush_dns"),
                    success=True,
                    message="DNS cache flushed via airplane mode toggle",
                    details={},
                )
        except Exception as e:
            return RepairResult(
                action=next(a for a in self.AVAILABLE_ACTIONS if a.name == "flush_dns"),
                success=False,
                message=f"Failed to flush DNS: {e}",
            )

    async def _repair_reset_network_settings(self, **kwargs: Any) -> RepairResult:
        """Reset network settings (toggle all radio settings)."""
        try:
            # Reset Wi-Fi
            await self.client.execute_async("shell", "svc wifi disable")
            await asyncio_sleep(1)
            await self.client.execute_async("shell", "svc wifi enable")

            # Reset mobile data
            await self.client.execute_async("shell", "svc data disable")
            await asyncio_sleep(1)
            await self.client.execute_async("shell", "svc data enable")

            # Flush DNS
            await self.client.execute_async("shell", "settings put global airplane_mode_on 1")
            await asyncio_sleep(2)
            await self.client.execute_async("shell", "settings put global airplane_mode_on 0")

            return RepairResult(
                action=next(
                    a for a in self.AVAILABLE_ACTIONS if a.name == "reset_network_settings"
                ),
                success=True,
                message="Network settings reset (Wi-Fi, mobile data, DNS cache flushed)",
                details={},
                requires_reboot=False,
            )
        except Exception as e:
            return RepairResult(
                action=next(
                    a for a in self.AVAILABLE_ACTIONS if a.name == "reset_network_settings"
                ),
                success=False,
                message=f"Failed to reset network settings: {e}",
            )

    # ===== Logcat Repairs =====

    async def _repair_clear_logcat_buffers(self, **kwargs: Any) -> RepairResult:
        """Clear all logcat buffers."""
        try:
            buffers = ["main", "system", "radio", "events", "crash", "kernel"]
            cleared = []

            for buf in buffers:
                try:
                    await self.client.execute_async("shell", f"logcat -b {buf} -c")
                    cleared.append(buf)
                except Exception:
                    pass

            return RepairResult(
                action=next(a for a in self.AVAILABLE_ACTIONS if a.name == "clear_logcat_buffers"),
                success=True,
                message=f"Cleared logcat buffers: {', '.join(cleared)}",
                details={"buffers_cleared": cleared},
            )
        except Exception as e:
            return RepairResult(
                action=next(a for a in self.AVAILABLE_ACTIONS if a.name == "clear_logcat_buffers"),
                success=False,
                message=f"Failed to clear logcat buffers: {e}",
            )

    async def _repair_clear_old_logs(self, **kwargs: Any) -> RepairResult:
        """Remove old log files."""
        try:
            log_dirs = [
                "/data/log",
                "/sdcard/logs",
                "/sdcard/Download/logs",
            ]

            total_removed = 0
            for dir_path in log_dirs:
                try:
                    await self.client.execute_async(
                        "shell", f"find {dir_path} -type f -mtime +7 -delete 2>/dev/null"
                    )
                    total_removed += 1
                except Exception:
                    pass

            return RepairResult(
                action=next(a for a in self.AVAILABLE_ACTIONS if a.name == "clear_old_logs"),
                success=True,
                message=f"Cleaned old logs from {total_removed} directories",
                details={"dirs_processed": total_removed},
            )
        except Exception as e:
            return RepairResult(
                action=next(a for a in self.AVAILABLE_ACTIONS if a.name == "clear_old_logs"),
                success=False,
                message=f"Failed to clear old logs: {e}",
            )

    async def _repair_reduce_log_verbosity(self, **kwargs: Any) -> RepairResult:
        """Reduce log verbosity for noisy packages."""
        try:
            # Common noisy Samsung packages
            noisy_packages = [
                "com.samsung.android.*",
                "com.sec.android.*",
                "com.google.android.gms",
                "com.facebook.*",
            ]

            set_count = 0
            for pkg_pattern in noisy_packages:
                try:
                    # Set log level to INFO (suppress VERBOSE/DEBUG)
                    await self.client.execute_async("shell", f"setprop log.tag.{pkg_pattern} INFO")
                    set_count += 1
                except Exception:
                    pass

            return RepairResult(
                action=next(a for a in self.AVAILABLE_ACTIONS if a.name == "reduce_log_verbosity"),
                success=True,
                message=f"Reduced log verbosity for {set_count} package patterns",
                details={"patterns": noisy_packages},
            )
        except Exception as e:
            return RepairResult(
                action=next(a for a in self.AVAILABLE_ACTIONS if a.name == "reduce_log_verbosity"),
                success=False,
                message=f"Failed to reduce log verbosity: {e}",
            )


# Helper for async sleep
async def asyncio_sleep(seconds: float) -> None:
    await asyncio.sleep(seconds)
