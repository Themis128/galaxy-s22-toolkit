"""Desktop toast notifications for the phone toolkit.

Windows toast notifications with optional Approve/Deny action buttons,
built on the optional ``windows-toasts`` package. Degrades gracefully:
``request_approval()`` raises :class:`ApprovalUnavailableError` when toasts
are not available so callers can fall back (e.g. to a console prompt).
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

try:  # pragma: no cover - import probe
    from windows_toasts import (
        InteractableWindowsToaster,
        Toast,
        ToastButton,
        ToastDuration,
        ToastScenario,
        WindowsToaster,
    )

    _HAS_WINDOWS_TOASTS = True
except ImportError:  # pragma: no cover
    _HAS_WINDOWS_TOASTS = False


class NotificationError(RuntimeError):
    """Raised when a toast notification could not be shown."""


class ApprovalUnavailableError(NotificationError):
    """Raised when interactive toast approval is not available."""


class DesktopNotifier:
    """Windows toast notifications, optionally with Approve/Deny buttons.

    Args:
        app_id: Toast sender identity shown in the notification.
        dashboard_url: Optional URL opened when a notification body is clicked.
    """

    def __init__(self, app_id: str = "Galaxy S22+ Toolkit", dashboard_url: str | None = None):
        self.app_id = app_id
        self.last_error: str | None = None
        self.dashboard_url = dashboard_url
        self._toaster: Any = None
        self._interactable: Any = None  # lazy toaster supporting buttons
        self._lock = threading.Lock()

    # ===== Fire-and-forget notifications =====

    def notify(self, title: str, message: str, long: bool = False) -> bool:
        """Show a plain toast notification. Returns True when shown."""
        if not _HAS_WINDOWS_TOASTS:
            self.last_error = "windows-toasts is not installed"
            return False
        try:
            with self._lock:
                if self._toaster is None:
                    self._toaster = WindowsToaster(self.app_id)
                toast = Toast(
                    [title, message],
                    duration=ToastDuration.Long if long else ToastDuration.Default,
                    on_activated=self._open_dashboard_on_click if self.dashboard_url else None,
                )
                self._toaster.show_toast(toast)
            return True
        except Exception as exc:  # WinRT can fail if notifications are blocked
            self.last_error = str(exc)
            logger.warning("Toast notification failed: %s", exc)
            return False

    # ===== Approval requests =====

    def request_approval(self, title: str, message: str, timeout_s: int = 120) -> bool:
        """Show a toast with Approve/Deny buttons and wait for the user.

        Blocks the calling thread until a button is clicked or the timeout
        expires. Timeout counts as denial (safe default for repairs).
        """
        if not _HAS_WINDOWS_TOASTS:
            raise ApprovalUnavailableError("windows-toasts is not installed")

        result = {"approved": False}
        event = threading.Event()

        def _activated(args: Any) -> None:
            arguments = str(getattr(args, "arguments", "") or "")
            result["approved"] = arguments == "approve"
            event.set()

        def _dismissed(_args: Any) -> None:
            # Explicit dismiss or OS expiry counts as denial
            event.set()

        def _failed(_args: Any) -> None:
            event.set()

        try:
            toast = Toast(
                [title, message],
                duration=ToastDuration.Long,
                scenario=ToastScenario.Reminder,  # stays on screen until user acts
                on_activated=_activated,
                on_dismissed=_dismissed,
                on_failed=_failed,
            )
            toast.AddAction(ToastButton("Approve", "approve"))
            toast.AddAction(ToastButton("Deny", "deny"))
            with self._lock:
                if self._interactable is None:
                    self._interactable = InteractableWindowsToaster(self.app_id)
                self._interactable.show_toast(toast)
            if not event.wait(timeout_s):
                logger.info("Toast approval timed out after %ss", timeout_s)
            return result["approved"]
        except ApprovalUnavailableError:
            raise
        except Exception as exc:
            self.last_error = str(exc)
            raise ApprovalUnavailableError(f"Toast approval failed: {exc}") from exc

    async def request_approval_async(self, title: str, message: str, timeout_s: int = 120) -> bool:
        """Async wrapper: runs the blocking toast wait off the event loop."""
        return await asyncio.to_thread(self.request_approval, title, message, timeout_s)

    def _open_dashboard_on_click(self, _args: Any) -> None:
        """Open the dashboard in the default browser when toast body is clicked."""
        try:
            import webbrowser

            if self.dashboard_url:
                webbrowser.open(self.dashboard_url)
        except Exception as exc:
            logger.debug("Could not open dashboard URL: %s", exc)
