"""Post-flash root verification."""

from __future__ import annotations

import argparse
import json


def cmd_verify(args: argparse.Namespace, client) -> int:
    """Confirm su/Magisk work, check Knox bits, sanity-check battery/storage."""
    root = client.root
    info = root.get_root_info()

    checks: list[dict] = []
    checks.append({"check": "su_available", "ok": info.rooted, "detail": info.su_path or "no su on PATH"})
    checks.append({
        "check": "magisk",
        "ok": bool(info.magisk_version),
        "detail": info.magisk_version or "Magisk not detected",
    })
    checks.append({
        "check": "knox",
        "ok": True,  # informational: Knox tripped is expected post-root
        "detail": info.knox_status,
    })
    checks.append({
        "check": "modules_dir",
        "ok": True,
        "detail": "present" if info.modules_dir_present else "no /data/adb/modules yet",
    })

    # Sanity: the flash should not have broken basics
    battery = client.battery.get_battery_info()
    storage = client.storage.get_storage_info()
    data_part = next((p for p in storage if p.mount_point == "/data"), storage[0] if storage else None)
    checks.append({"check": "battery_readable", "ok": battery.level > 0, "detail": f"{battery.level}%"})
    checks.append({
        "check": "storage_readable",
        "ok": bool(data_part and data_part.total_bytes > 0),
        "detail": f"{data_part.used_gb:.1f}/{data_part.total_gb:.1f} GB used on /data" if data_part else "no partitions",
    })

    result = {
        "rooted": info.rooted,
        "magisk_version": info.magisk_version,
        "knox_status": info.knox_status,
        "checks": checks,
        "play_integrity": (
            "Open Play Store > Settings > About and confirm the device passes; "
            "if not, install PlayIntegrityFix (see `phone-root modules recommend`)."
        ),
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("Post-flash verification")
        print("=" * 50)
        for c in checks:
            mark = "PASS" if c["ok"] else "FAIL"
            print(f"  [{mark:4}] {c['check']:18} {c['detail']}")
        print("=" * 50)
        print("Root:", "WORKING" if info.rooted else "NOT DETECTED")
        print("\nPlay Integrity: " + result["play_integrity"])

    return 0 if info.rooted else 1
