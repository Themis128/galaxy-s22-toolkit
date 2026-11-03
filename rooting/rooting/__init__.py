"""phone-root — guarded root-support CLI for the Galaxy S22+ toolkit."""

from __future__ import annotations

import argparse
import sys

from rooting import backup, modules, preflight, verify


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="phone-root",
        description=(
            "Guarded root support for Galaxy S22+ (SM-S906B). "
            "Bootloader/Odin operations are manual-only — see rooting/RUNBOOK.md."
        ),
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--serial", "-s", help="Device serial (default: auto-detect)")
    common.add_argument("--json", "-j", action="store_true", help="JSON output")
    parser.add_argument("--serial", "-s", help="Device serial (default: auto-detect)")
    parser.add_argument("--json", "-j", action="store_true", help="JSON output")
    sub = parser.add_subparsers(dest="command")

    pf = sub.add_parser("preflight", parents=[common], help="Root-readiness check (GO/NO-GO)")
    pf.set_defaults(func=preflight.cmd_preflight)

    bk = sub.add_parser("backup", parents=[common], help="Full pre-flash backup to data/backup-<ts>/")
    bk.add_argument("--dry-run", action="store_true", help="List planned actions only")
    bk.add_argument("--yes", "-y", action="store_true", help="Confirm write operations")
    bk.add_argument("--no-media", action="store_true", help="Skip DCIM/Download media pull")
    bk.set_defaults(func=backup.cmd_backup)

    vf = sub.add_parser("verify", parents=[common], help="Post-flash root verification")
    vf.set_defaults(func=verify.cmd_verify)

    md = sub.add_parser("modules", parents=[common], help="Magisk module management")
    md.add_argument(
        "action",
        choices=["list", "install", "enable", "disable", "remove", "recommend"],
        help="Module action",
    )
    md.add_argument("module", nargs="?", help="Module id or zip path (install)")
    md.add_argument("--yes", "-y", action="store_true", help="Confirm mutating actions")
    md.set_defaults(func=modules.cmd_modules)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    from phone import DeviceNotFoundError, create_client

    try:
        # create_client() pins the toolkit's known serial, avoiding adb's
        # ambiguous-device error when an offline emulator is also attached.
        client = create_client(serial=args.serial) if args.serial else create_client()
        if not client.is_connected:
            print("Error: No device connected", file=sys.stderr)
            sys.exit(3)
        sys.exit(args.func(args, client))
    except DeviceNotFoundError:
        print("Error: Device not found. Check USB debugging and cable.", file=sys.stderr)
        sys.exit(3)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
