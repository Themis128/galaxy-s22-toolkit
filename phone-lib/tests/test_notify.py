"""Unit tests for the notify module (mocked toasts)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import phone.notify as notify_mod
from phone.notify import ApprovalUnavailableError, DesktopNotifier


def _fake_toast_factory(*args, **kw):
    return SimpleNamespace(
        AddAction=lambda *a: None,
        on_activated=kw.get("on_activated"),
        on_dismissed=kw.get("on_dismissed"),
        on_failed=kw.get("on_failed"),
    )


def _patch_toasts(monkeypatch, click: str | None = "approve") -> None:
    """Patch windows_toasts names in phone.notify with test doubles."""

    class FakeInteractable:
        def __init__(self, app_id):
            self.app_id = app_id

        def show_toast(self, toast):
            if click:
                toast.on_activated(SimpleNamespace(arguments=click))

    monkeypatch.setattr(notify_mod, "_HAS_WINDOWS_TOASTS", True)
    monkeypatch.setattr(notify_mod, "InteractableWindowsToaster", FakeInteractable)
    monkeypatch.setattr(notify_mod, "Toast", _fake_toast_factory)


@pytest.fixture
def notifier() -> DesktopNotifier:
    return DesktopNotifier(app_id="unit-test")


class TestAvailability:
    def test_notify_false_without_windows_toasts(self, notifier, monkeypatch):
        monkeypatch.setattr(notify_mod, "_HAS_WINDOWS_TOASTS", False)
        assert notifier.notify("t", "m") is False
        assert notifier.last_error is not None

    def test_approval_raises_without_windows_toasts(self, notifier, monkeypatch):
        monkeypatch.setattr(notify_mod, "_HAS_WINDOWS_TOASTS", False)
        with pytest.raises(ApprovalUnavailableError):
            notifier.request_approval("t", "m", timeout_s=1)


class TestApprovalFlow:
    def test_approve_click(self, notifier, monkeypatch):
        _patch_toasts(monkeypatch, click="approve")
        assert notifier.request_approval("t", "m", timeout_s=5) is True

    def test_deny_click(self, notifier, monkeypatch):
        _patch_toasts(monkeypatch, click="deny")
        assert notifier.request_approval("t", "m", timeout_s=5) is False

    def test_timeout_denies(self, notifier, monkeypatch):
        _patch_toasts(monkeypatch, click=None)
        assert notifier.request_approval("t", "m", timeout_s=0) is False

    def test_show_failure_raises(self, notifier, monkeypatch):
        class FailingToaster:
            def show_toast(self, toast):
                raise OSError("notifications blocked")

        monkeypatch.setattr(notify_mod, "_HAS_WINDOWS_TOASTS", True)
        monkeypatch.setattr(notify_mod, "InteractableWindowsToaster", FailingToaster)
        monkeypatch.setattr(notify_mod, "Toast", _fake_toast_factory)
        with pytest.raises(ApprovalUnavailableError):
            notifier.request_approval("t", "m", timeout_s=5)
