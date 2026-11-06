"""Unit tests for apps module."""

from __future__ import annotations

from phone.apps import AppsModule
from phone.models import AppInfo


class TestAppsModule:
    """Tests for AppsModule."""

    def test_list_packages_all(self, mock_adb_client):
        """Test listing all packages."""
        module = AppsModule(mock_adb_client)
        packages = module.list_packages()

        assert len(packages) == 5
        assert "com.android.systemui" in packages
        assert "com.example.app" in packages

    def test_list_packages_third_party(self, mock_adb_client):
        """Test listing third-party packages only."""
        module = AppsModule(mock_adb_client)
        packages = module.list_packages(third_party=True)

        assert len(packages) == 2
        assert "com.example.app" in packages
        assert "com.another.app" in packages

    def test_list_packages_disabled(self, mock_adb_client):
        """Test listing disabled packages."""
        module = AppsModule(mock_adb_client)
        packages = module.list_packages(disabled=True)

        assert len(packages) == 1
        assert "com.bloatware.app" in packages

    def test_list_packages_enabled(self, mock_adb_client):
        """Test listing enabled packages."""
        module = AppsModule(mock_adb_client)
        packages = module.list_packages(enabled=True)

        assert len(packages) == 4
        assert "com.example.app" in packages

    def test_get_app_info(self, mock_adb_client):
        """Test getting detailed app info."""
        module = AppsModule(mock_adb_client)
        app = module.get_app_info("com.example.app")

        assert isinstance(app, AppInfo)
        assert app.package_name == "com.example.app"
        assert app.version_name == "1.2.3"
        assert app.version_code == 45
        assert app.enabled is True
        assert app.system_app is False
        assert "android.permission.INTERNET" in app.permissions
        assert "android.permission.CAMERA" in app.permissions

    def test_is_app_installed(self, mock_adb_client):
        """Test checking if app is installed."""
        module = AppsModule(mock_adb_client)

        assert module.is_app_installed("com.example.app") is True
        assert module.is_app_installed("com.nonexistent.app") is False

    def test_is_app_enabled(self, mock_adb_client):
        """Test checking if app is enabled."""
        module = AppsModule(mock_adb_client)

        assert module.is_app_enabled("com.example.app") is True
        assert module.is_app_enabled("com.bloatware.app") is False

    def test_get_running_apps(self, mock_adb_client):
        """Test getting running apps."""
        module = AppsModule(mock_adb_client)
        running = module.get_running_apps()

        assert len(running) == 2
        assert "com.example.app" in running
        assert "com.another.app" in running

    def test_get_pid(self, mock_adb_client):
        """Test getting app PID."""
        mock_adb_client.execute.return_value = "1234"
        module = AppsModule(mock_adb_client)
        pid = module.get_pid("com.example.app")

        assert pid == 1234

    def test_get_uid(self, mock_adb_client):
        """Test getting app UID."""
        module = AppsModule(mock_adb_client)
        uid = module.get_uid("com.example.app")

        assert uid == 10123

    def test_clear_app_cache(self, mock_adb_client):
        """Test clearing app cache."""
        module = AppsModule(mock_adb_client)
        result = module.clear_app_cache("com.example.app")

        assert result is True
        mock_adb_client.execute.assert_called_with(
            "shell", "pm", "clear", "--cache-only", "com.example.app"
        )

    def test_start_app(self, mock_adb_client):
        """Test starting app."""
        module = AppsModule(mock_adb_client)
        result = module.start_app("com.example.app")

        assert result is True

    def test_stop_app(self, mock_adb_client):
        """Test force stopping app."""
        module = AppsModule(mock_adb_client)
        result = module.stop_app("com.example.app")

        assert result is True
        mock_adb_client.execute.assert_called_with("shell", "am", "force-stop", "com.example.app")

    def test_restart_app(self, mock_adb_client):
        """Test restarting app."""
        module = AppsModule(mock_adb_client)
        result = module.restart_app("com.example.app")

        assert result is True

    def test_grant_permission(self, mock_adb_client):
        """Test granting permission."""
        module = AppsModule(mock_adb_client)
        result = module.grant_permission("com.example.app", "android.permission.CAMERA")

        assert result is True
        mock_adb_client.execute.assert_called_with(
            "shell", "pm", "grant", "com.example.app", "android.permission.CAMERA"
        )

    def test_revoke_permission(self, mock_adb_client):
        """Test revoking permission."""
        module = AppsModule(mock_adb_client)
        result = module.revoke_permission("com.example.app", "android.permission.CAMERA")

        assert result is True
        mock_adb_client.execute.assert_called_with(
            "shell", "pm", "revoke", "com.example.app", "android.permission.CAMERA"
        )

    def test_backup_app(self, mock_adb_client):
        """Test backing up app APK."""
        module = AppsModule(mock_adb_client)
        result = module.backup_app("com.example.app", "./backups")

        assert result is True


class TestRunningAppsAndroid16:
    """`cmd activity top` was removed on Android 16 - the dumpsys fallback must engage."""

    PROCDUMP = (
        "    Proc #65: psvc   F/ /PER  LCMNFUAT  t: 0 5989:com.sec.imsservice:ImsUpdateService/1000 (service)\n"
        "    Proc #76: vis    F/S/FGS  ---NFU-T  t: 0 20049:com.tailscale.ipn/u0a387 (service)\n"
        "    Proc #33: psvc   F/ /PER  LCMNFUAT  t: 0 6886:com.google.android.providers.media.module/u0a327 (service)\n"
        "    Proc # 3: psvc   F/ /PER  LCMNFUAT  t: 0 4073:com.android.bluetooth/1002 (service)\n"
    )

    def _mock(self, client, top_output: str) -> None:
        from unittest.mock import MagicMock

        def execute(*args, **kwargs):
            if args[:3] == ("shell", "cmd", "activity"):
                return top_output
            if args[:3] == ("shell", "dumpsys", "activity"):
                return self.PROCDUMP
            return ""

        client.execute = MagicMock(side_effect=execute)

    def test_unknown_command_falls_back_to_dumpsys(self, mock_adb_client):
        """'Unknown command: top' routes to the dumpsys activity processes parser."""
        module = AppsModule(mock_adb_client)
        self._mock(mock_adb_client, "Unknown command: top\n")
        apps = module.get_running_apps()
        assert "com.sec.imsservice" in apps
        assert "com.tailscale.ipn" in apps
        assert "com.google.android.providers.media.module" in apps
        assert "psvc" not in apps  # state tokens must not leak in
        assert apps == sorted(set(apps))

    def test_empty_top_output_falls_back(self, mock_adb_client):
        """Empty top output also routes to the fallback."""
        module = AppsModule(mock_adb_client)
        self._mock(mock_adb_client, "")
        apps = module.get_running_apps()
        assert "com.android.bluetooth" in apps

    def test_legacy_top_output_still_parsed(self, mock_adb_client):
        """Older Androids keep the package/activity parser (no fallback run)."""
        module = AppsModule(mock_adb_client)
        self._mock(
            mock_adb_client,
            "ACTIVITY MANAGER RUNNING ACTIVITIES\n  TaskRecord{1234 com.example.app}\n"
            "    com.another.app/.MainActivity\n",
        )
        apps = module.get_running_apps()
        assert "com.example.app" in apps
        assert "com.another.app/.MainActivity" in apps
        calls = [c.args for c in mock_adb_client.execute.call_args_list]
        assert not any(a[:3] == ("shell", "dumpsys", "activity") for a in calls)
