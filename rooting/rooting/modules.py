"""Magisk module management + curated recommendations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from phone.exceptions import PhoneError

RECOMMENDED = [
    {
        "name": "PlayIntegrityFix",
        "why": "Pass Play Integrity so banking apps and the Play Store keep working",
        "source": "https://github.com/chiteroman/PlayIntegrityFix",
    },
    {
        "name": "Shamiko",
        "why": "Hide root from apps on Magisk DenyList (pairs with DenyList config)",
        "source": "https://github.com/LSPosed/LSPosed.github.io/releases",
    },
    {
        "name": "Systemless Debloater",
        "why": "Remove Samsung bloat systemlessly (reversible via /data/adb/modules)",
        "source": "https://xdaforums.com/t/magisk-module-systemless-debloater.4180083/",
    },
    {
        "name": "LSPosed (maintained fork)",
        "why": "Xposed framework for per-app behavior tweaks (Zygisk-based)",
        "source": "https://github.com/mywalkb/LSPosed_mod",
    },
]


def cmd_modules(args: argparse.Namespace, client) -> int:
    """list | install | enable | disable | remove | recommend."""
    root = client.root

    if args.action == "recommend":
        if getattr(args, "json", False):
            print(json.dumps(RECOMMENDED, indent=2))
        else:
            print("Recommended modules for this device:")
            for m in RECOMMENDED:
                print(f"\n  {m['name']}\n    why:    {m['why']}\n    source: {m['source']}")
        return 0

    if args.action == "list":
        mods = root.list_modules()
        if getattr(args, "json", False):
            print(json.dumps(mods, indent=2))
        elif not mods:
            print("No modules installed (or device not rooted).")
        else:
            for m in mods:
                state = " [disabled]" if m["disabled"] else ""
                state += " [remove-pending]" if m["pending_removal"] else ""
                print(f"  {m['id']:40}{state}")
            print(f"\nTotal: {len(mods)} module(s)")
        return 0

    if args.action == "install":
        if not args.module:
            print("Usage: phone-root modules install <path/to/module.zip>", file=sys.stderr)
            return 2
        if not args.yes:
            print("Refusing without --yes (installs a Magisk module).")
            return 2
        zip_path = args.module
        if not Path(zip_path).exists():
            print(f"Module zip not found: {zip_path}", file=sys.stderr)
            return 1
        remote = f"/data/local/tmp/{Path(zip_path).name}"
        client.push(zip_path, remote)
        out = root.run_privileged(f"magisk --install-module {remote}", confirm=True)
        print(out.strip() or "Module install requested; reboot to activate.")
        return 0

    # enable | disable | remove
    if not args.module:
        print(f"Usage: phone-root modules {args.action} <module-id>", file=sys.stderr)
        return 2
    if not args.yes:
        print(f"Refusing without --yes (module {args.action} takes effect after reboot).")
        return 2
    try:
        root.set_module_state(args.module, args.action, confirm=True)
    except PhoneError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Module '{args.module}' {args.action}d. Reboot to apply.")
    return 0
