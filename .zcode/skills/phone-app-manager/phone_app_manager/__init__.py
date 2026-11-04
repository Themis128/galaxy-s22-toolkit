"""Phone App Manager Skill Implementation."""

from __future__ import annotations

import argparse
import json
import sys

from phone import AdbClient


def list_apps(args: argparse.Namespace, client: AdbClient) -> int:
    """List installed apps."""
    mods = client.apps

    if args.json:
        apps = mods.list_apps(only_enabled=not args.disabled)
        print(json.dumps([a.model for a in apps], indent=2, default=str))
        return 0

    print("Installed apps:")
    apps = mods.list_apps(only_enabled=not args.disabled)

    for i, app in enumerate(apps, 1):
        flags = []
        if app.system_app:
            flags.append("SYSTEM")
        if app.enabled:
            flags.append("ENABLED")
        if "DEBUGGABLE" in app.flags:
            flags.append("DEBUG")

        flag_str = f" [{', '.join(flags)}]" if flags else ""
        print(f"{i:3}. {app.package_name:40} {app.app_name}{flag_str}")

    print(f"\nTotal: {len(apps)} apps")
    return 0


def clear_app(args: argparse.Namespace, client: AdbClient) -> int:
    """Clear app data/cache."""
    package = args.package

    try:
        app_info = client.apps.get_app_info(package)
        if not app_info:
            print(f"App not found: {package}", file=sys.stderr)
            return 1

        client.execute("shell", "pm", "clear", package)
        print(f"Cleared: {package} (data + cache)")
        return 0
    except Exception as e:
        print(f"Error clearing app: {e}", file=sys.stderr)
        return 1


def uninstall_app(args: argparse.Namespace, client: AdbClient) -> int:
    """Uninstall an app."""
    package = args.package

    try:
        client.apps.uninstall(package)
        print(f"Uninstalled: {package}")
        return 0
    except Exception as e:
        print(f"Error uninstalling app: {e}", file=sys.stderr)
        return 1


def disable_app(args: argparse.Namespace, client: AdbClient) -> int:
    """Disable an app (freeze)."""
    package = args.package

    try:
        client.apps.disable(package)
        print(f"Disabled: {package}")
        return 0
    except Exception as e:
        print(f"Error disabling app: {e}", file=sys.stderr)
        return 1


def enable_app(args: argparse.Namespace, client: AdbClient) -> int:
    """Enable a disabled app (unfreeze)."""
    package = args.package

    try:
        client.apps.enable(package)
        print(f"Enabled: {package}")
        return 0
    except Exception as e:
        print(f"Error enabling app: {e}", file=sys.stderr)
        return 1


def show_app_info(args: argparse.Namespace, client: AdbClient) -> int:
    """Show detailed info about an app."""
    package = args.package

    try:
        app_info = client.apps.get_app_info(package)
        if not app_info:
            print(f"App not found: {package}", file=sys.stderr)
            return 1

        print(f"\nApp: {app_info.app_name}")
        print(f"Package: {app_info.package_name}")
        print(f"Version: {app_info.version_name}")
        print(f"Code: {app_info.version_code}")
        print(f"Enabled: {app_info.is_enabled}")
        print(f"System: {app_info.is_system_app}")
        print(f"Debuggable: {app_info.is_debuggable}")

        if args.json:
            print("\nJSON:")
            print(json.dumps([app_info.model], indent=2, default=str))

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Phone App Manager")
    parser.add_argument("--serial", help="Device serial")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # List command
    list_parser = subparsers.add_parser("list", help="List apps")
    list_parser.add_argument("--disabled", action="store_true", help="Include disabled apps")
    list_parser.add_argument("--json", action="store_true")
    list_parser.set_defaults(func=list_apps)

    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Clear app data")
    clear_parser.add_argument("package", help="Package name")
    clear_parser.set_defaults(func=clear_app)

    # Uninstall command
    uninstall_parser = subparsers.add_parser("uninstall", help="Uninstall app")
    uninstall_parser.add_argument("package", help="Package name")
    uninstall_parser.set_defaults(func=uninstall_app)

    # Disable command
    disable_parser = subparsers.add_parser("disable", help="Disable/freeze app")
    disable_parser.add_argument("package", help="Package name")
    disable_parser.set_defaults(func=disable_app)

    # Enable command
    enable_parser = subparsers.add_parser("enable", help="Enable app/unfreeze")
    enable_parser.add_argument("package", help="Package name")
    enable_parser.set_defaults(func=enable_app)

    # Info command
    info_parser = subparsers.add_parser("info", help="Show app info")
    info_parser.add_argument("package", help="Package name")
    info_parser.add_argument("--json", action="store_true")
    info_parser.set_defaults(func=show_app_info)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    client = AdbClient(serial=args.serial) if args.serial else AdbClient()

    if not client.is_connected:
        print("Error: No device connected", file=sys.stderr)
        sys.exit(3)

    try:
        if hasattr(args, 'func'):
            sys.exit(args.func(args, client))
        else:
            parser.print_help()
            sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(4)


if __name__ == "__main__":
    main()
