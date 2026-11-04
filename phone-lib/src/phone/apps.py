"""Application package management."""

from __future__ import annotations

import re
from datetime import datetime

from .adb import AdbClient
from .models import AppInfo


class AppsModule:
    """Application management module."""

    def __init__(self, client: AdbClient) -> None:
        self.client = client

    def list_packages(
        self,
        system: bool = False,
        third_party: bool = False,
        enabled: bool = False,
        disabled: bool = False,
        filter_pattern: str | None = None,
    ) -> list[str]:
        """List installed packages."""
        args = ["shell", "pm", "list", "packages"]
        if system:
            args.append("-s")
        if third_party:
            args.append("-3")
        if enabled:
            args.append("-e")
        if disabled:
            args.append("-d")

        output = self.client.execute(*args)
        packages = []
        for line in output.strip().split("\n"):
            if line.startswith("package:"):
                pkg = line[8:].strip()
                if filter_pattern is None or filter_pattern in pkg:
                    packages.append(pkg)
        return packages

    def list_apps(self, only_enabled: bool = True) -> list[AppInfo]:
        """List installed apps with detailed info (for diagnostics compatibility)."""
        packages = self.list_packages(third_party=not only_enabled)
        apps = []
        for pkg in packages:
            info = self.get_app_info(pkg)
            if info:
                apps.append(info)
        return apps

    def get_app_info(self, package_name: str) -> AppInfo | None:
        """Get detailed information about an app."""
        try:
            output = self.client.execute("shell", "dumpsys", "package", package_name)
            return self._parse_package_info(package_name, output)
        except Exception:
            return None

    def _parse_package_info(self, package_name: str, output: str) -> AppInfo:
        """Parse dumpsys package output."""
        info = AppInfo(package_name=package_name)

        # Extract version info
        version_match = re.search(r"versionName=([^\s]+)", output)
        if version_match:
            info.version_name = version_match.group(1)

        code_match = re.search(r"versionCode=(\d+)", output)
        if code_match:
            info.version_code = int(code_match.group(1))

        # Extract install/update times
        install_match = re.search(r"firstInstallTime=(\d+)", output)
        if install_match:
            info.install_time = datetime.fromtimestamp(int(install_match.group(1)) / 1000)

        update_match = re.search(r"lastUpdateTime=(\d+)", output)
        if update_match:
            info.update_time = datetime.fromtimestamp(int(update_match.group(1)) / 1000)

        # Extract flags
        app_name = None
        for line in output.split("\n"):
            line = line.strip()
            if line == "PackageSignatures:":
                break
            if "flags=[" in line:
                flags_str = line.split("flags=[")[1].split("]")[0]
                info.flags = [f.strip() for f in flags_str.split(",") if f.strip()]

            if "installer=" in line:
                info.install_source = line.split("installer=")[1].strip()

            if "label=" in line and app_name is None:
                # Extract app name from label=...
                label_str = line.split("label=")[1].strip()
                if label_str.startswith('"') and label_str.endswith('"'):
                    label_str = label_str[1:-1]
                app_name = label_str

        info.app_name = app_name

        # Check if system app
        info.system_app = "SYSTEM" in info.flags or "UPDATED_SYSTEM_APP" in info.flags

        # Check if enabled
        info.enabled = "ENABLED" in info.flags or "DISABLED" not in info.flags

        # Get permissions
        info.permissions = self.get_app_permissions(package_name)

        return info

    def get_app_permissions(self, package_name: str) -> list[str]:
        """Get granted permissions for an app."""
        try:
            output = self.client.execute("shell", "dumpsys", "package", package_name)
            permissions = []
            in_permissions = False
            for line in output.split("\n"):
                line = line.strip()
                if "grantedPermissions:" in line:
                    in_permissions = True
                    continue
                if in_permissions:
                    # Check if line is a permission (starts with android.permission.)
                    if line.startswith("android.permission."):
                        permissions.append(line)
                    # Stop when we hit a non-indented line (new section)
                    elif line and not line.startswith(" "):
                        break
            return permissions
        except Exception:
            return []

    def is_app_installed(self, package_name: str) -> bool:
        """Check if an app is installed."""
        try:
            output = self.client.execute("shell", "pm", "list", "packages", package_name)
            return f"package:{package_name}" in output
        except Exception:
            return False

    def is_app_enabled(self, package_name: str) -> bool:
        """Check if an app is enabled."""
        try:
            output = self.client.execute("shell", "dumpsys", "package", package_name)
            return "enabled=2" not in output and "DISABLED" not in output
        except Exception:
            return True

    def enable_app(self, package_name: str) -> bool:
        """Enable an app."""
        try:
            self.client.execute("shell", "pm", "enable", package_name)
            return True
        except Exception:
            return False

    def disable_app(self, package_name: str) -> bool:
        """Disable an app (freeze)."""
        try:
            self.client.execute("shell", "pm", "disable-user", package_name)
            return True
        except Exception:
            return False

    def uninstall_app(self, package_name: str, keep_data: bool = False) -> bool:
        """Uninstall an app."""
        try:
            args = ["shell", "pm", "uninstall"]
            if keep_data:
                args.append("-k")
            args.append(package_name)
            self.client.execute(*args)
            return True
        except Exception:
            return False

    def install_app(
        self, apk_path: str, replace: bool = True, grant_permissions: bool = False
    ) -> bool:
        """Install an APK."""
        try:
            args = ["install"]
            if replace:
                args.append("-r")
            if grant_permissions:
                args.append("-g")
            args.append(apk_path)
            self.client.execute(*args)
            return True
        except Exception:
            return False

    def clear_app_data(self, package_name: str) -> bool:
        """Clear app data (cache + data)."""
        try:
            self.client.execute("shell", "pm", "clear", package_name)
            return True
        except Exception:
            return False

    def clear_app_cache(self, package_name: str) -> bool:
        """Clear app cache only."""
        try:
            self.client.execute("shell", "pm", "clear", "--cache-only", package_name)
            return True
        except Exception:
            return False

    def grant_permission(self, package_name: str, permission: str) -> bool:
        """Grant a permission to an app."""
        try:
            self.client.execute("shell", "pm", "grant", package_name, permission)
            return True
        except Exception:
            return False

    def revoke_permission(self, package_name: str, permission: str) -> bool:
        """Revoke a permission from an app."""
        try:
            self.client.execute("shell", "pm", "revoke", package_name, permission)
            return True
        except Exception:
            return False

    def grant_common_permissions(self, package_name: str) -> list[str]:
        """Grant common permissions to an app."""
        common_perms = [
            "android.permission.READ_EXTERNAL_STORAGE",
            "android.permission.WRITE_EXTERNAL_STORAGE",
            "android.permission.CAMERA",
            "android.permission.RECORD_AUDIO",
            "android.permission.ACCESS_FINE_LOCATION",
            "android.permission.ACCESS_COARSE_LOCATION",
            "android.permission.READ_CONTACTS",
            "android.permission.WRITE_CONTACTS",
        ]
        granted = []
        for perm in common_perms:
            if self.grant_permission(package_name, perm):
                granted.append(perm)
        return granted

    def start_app(self, package_name: str, activity: str | None = None) -> bool:
        """Start an app."""
        try:
            if activity:
                self.client.execute("shell", "am", "start", "-n", f"{package_name}/{activity}")
            else:
                self.client.execute(
                    "shell",
                    "monkey",
                    "-p",
                    package_name,
                    "-c",
                    "android.intent.category.LAUNCHER",
                    "1",
                )
            return True
        except Exception:
            return False

    def stop_app(self, package_name: str) -> bool:
        """Force stop an app."""
        try:
            self.client.execute("shell", "am", "force-stop", package_name)
            return True
        except Exception:
            return False

    def restart_app(self, package_name: str, activity: str | None = None) -> bool:
        """Restart an app."""
        self.stop_app(package_name)
        import time

        time.sleep(1)
        return self.start_app(package_name, activity)

    def get_running_apps(self) -> list[str]:
        """Get currently running apps."""
        try:
            output = self.client.execute("shell", "cmd", "activity", "top")
            packages = []
            for line in output.split("\n"):
                # Match both formats: package/activity and TaskRecord{...}
                match = re.search(r"([a-zA-Z0-9_.]+/[a-zA-Z0-9_.]+)", line)
                if match:
                    packages.append(match.group(1))
                else:
                    # Also match TaskRecord{id package}
                    match = re.search(r"TaskRecord\{[^}]+\s+([a-zA-Z0-9_.]+)", line)
                    if match:
                        packages.append(match.group(1))
            return list(set(packages))
        except Exception:
            return []

    def get_app_pid(self, package_name: str) -> int | None:
        """Get app PID if running."""
        try:
            output = self.client.execute("shell", "pidof", package_name)
            pid_str = output.strip()
            return int(pid_str) if pid_str else None
        except Exception:
            return None

    def get_pid(self, package_name: str) -> int | None:
        """Get app PID if running (alias for get_app_pid)."""
        return self.get_app_pid(package_name)

    def get_app_uid(self, package_name: str) -> int | None:
        """Get app UID."""
        try:
            output = self.client.execute("shell", "dumpsys", "package", package_name)
            match = re.search(r"userId=(\d+)", output)
            return int(match.group(1)) if match else None
        except Exception:
            return None

    def get_uid(self, package_name: str) -> int | None:
        """Get app UID (alias for get_app_uid)."""
        return self.get_app_uid(package_name)

    def get_all_app_info(self, third_party_only: bool = True) -> list[AppInfo]:
        """Get info for all apps."""
        packages = self.list_packages(third_party=third_party_only)
        apps = []
        for pkg in packages:
            info = self.get_app_info(pkg)
            if info:
                apps.append(info)
        return apps

    def backup_app(self, package_name: str, output_path: str = ".") -> bool:
        """Backup app APK (requires root for system apps)."""
        try:
            info = self.get_app_info(package_name)
            if not info:
                return False

            # Get APK path
            output = self.client.execute("shell", "pm", "path", package_name)
            apk_path = output.replace("package:", "").strip()

            if apk_path:
                self.client.pull(apk_path, output_path)
                return True
        except Exception:
            pass
        return False
