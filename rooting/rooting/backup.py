"""Pre-flash backup: everything worth keeping before the bootloader wipe."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

# Backups land under <cwd>/data/ so the CLI behaves the same from any install
# location; run phone-root from the project root.
DATA_ROOT = Path.cwd() / "data"
MEDIA_DIRS = ["/sdcard/DCIM", "/sdcard/Download", "/sdcard/Pictures"]
SETTINGS_NAMESPACES = ["system", "secure", "global"]


def _app_inventory(client) -> list[dict]:
    apps = client.apps.list_apps(only_enabled=False)
    return [a.model for a in apps]


def _pull_apks(client, out_dir: Path) -> list[str]:
    """Pull the base APK of every installed app."""
    pulled = []
    packages = client.apps.list_packages()
    for pkg in packages:
        try:
            raw = client.execute("shell", "pm path", pkg).strip()
            apk = raw.replace("package:", "").split(":")[0].strip()
            if apk:
                local = out_dir / "apks" / f"{pkg}.apk"
                local.parent.mkdir(parents=True, exist_ok=True)
                client.pull(apk, str(local))
                pulled.append(pkg)
        except Exception as exc:  # noqa: BLE001 - best-effort backup
            pulled.append(f"{pkg} (failed: {exc})")
    return pulled


def _export_settings(client, out_dir: Path) -> None:
    for ns in SETTINGS_NAMESPACES:
        raw = client.execute("shell", f"settings list {ns}")
        (out_dir / f"settings-{ns}.txt").write_text(raw, encoding="utf-8")


def _export_content_table(client, uri: str, out_file: Path) -> int:
    """Export a content provider table via content query."""
    try:
        raw = client.execute("shell", "content", "query", "--uri", uri)
        out_file.write_text(raw, encoding="utf-8")
        return raw.count("\n") + (0 if raw.endswith("\n") or not raw else 1)
    except Exception:
        out_file.write_text("", encoding="utf-8")
        return 0


def _pull_media(client, out_dir: Path) -> None:
    for remote in MEDIA_DIRS:
        local = out_dir / "media" / remote.rstrip("/").split("/")[-1]
        try:
            client.pull(remote, str(local))
        except Exception as exc:  # noqa: BLE001 - missing dirs are fine
            print(f"  skip {remote}: {exc}")


def cmd_backup(args: argparse.Namespace, client) -> int:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = DATA_ROOT / f"backup-{stamp}"
    plan = [
        f"Create {out_dir}",
        "Export app inventory (packages + versions + permissions) -> apps.json",
        "Export settings (system/secure/global) -> settings-*.txt",
        "Export contacts, SMS, call log via content query -> content-*.txt",
        "Pull base APK of every installed app -> apks/",
        *(["Pull media: " + ", ".join(MEDIA_DIRS) + " -> media/"] if not args.no_media else []),
        "Write BACKUP-MANIFEST.json",
    ]

    if args.dry_run:
        print("Planned backup actions:")
        for item in plan:
            print(f"  - {item}")
        print(f"\nDestination: {out_dir} (nothing written)")
        return 0

    if not args.yes:
        print(
            "Refusing to run without --yes (writes files, takes several minutes).\n"
            "Preview with: phone-root backup --dry-run"
        )
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    print(f"Backing up to {out_dir}")

    print("  [1/6] App inventory...")
    apps = _app_inventory(client)
    (out_dir / "apps.json").write_text(json.dumps(apps, indent=2, default=str), encoding="utf-8")

    print("  [2/6] Settings export...")
    _export_settings(client, out_dir)

    print("  [3/6] Content tables (contacts/SMS/call log)...")
    for name, uri in [
        ("contacts", "content://com.android.contacts/contacts"),
        ("sms", "content://sms"),
        ("calllog", "content://call_log/calls"),
    ]:
        n = _export_content_table(client, uri, out_dir / f"content-{name}.txt")
        print(f"        {name}: {n} rows")

    print("  [4/6] APK pull (best-effort)...")
    pulled = _pull_apks(client, out_dir)
    print(f"        {len(pulled)} app APKs handled")

    if not args.no_media:
        print("  [5/6] Media pull...")
        _pull_media(client, out_dir)
    else:
        print("  [5/6] Media pull skipped (--no-media)")

    print("  [6/6] Manifest...")
    (out_dir / "BACKUP-MANIFEST.json").write_text(
        json.dumps(
            {
                "timestamp": stamp,
                "serial": getattr(client, "serial", None),
                "apps": len(apps),
                "apks_pulled": len(pulled),
                "media": not args.no_media,
                "duration_s": round(time.time() - started, 1),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Backup complete: {out_dir}")
    return 0
