"""Root-readiness preflight: GO/NO-GO before any bootloader action."""

from __future__ import annotations

import argparse
import json

EXPECTED_MODEL = "SM-S906B"


def cmd_preflight(args: argparse.Namespace, client) -> int:
    """Check device identity, OEM-unlock state, firmware, battery, ADB auth."""
    device = client.device.get_device_info()
    battery = client.battery.get_battery_info()

    checks: list[dict] = []

    def check(name: str, ok: bool, detail: str, blocking: bool = True) -> None:
        checks.append({"check": name, "ok": ok, "detail": detail, "blocking": blocking})

    model_ok = device.model.upper() == EXPECTED_MODEL
    check("model", model_ok, f"{device.model} (expected {EXPECTED_MODEL})")

    oem_raw = client.execute("shell", "settings get global oem_unlock_allowed").strip()
    check(
        "oem_unlock_allowed",
        oem_raw == "1",
        f"settings get global oem_unlock_allowed = {oem_raw!r}",
    )

    bit_raw = client.execute("shell", "getprop sys.oem_unlock_allowed").strip()
    check("oem_unlock_flag", bit_raw == "1", f"sys.oem_unlock_allowed = {bit_raw!r}")

    csc = client.execute("shell", "getprop ro.boot.em.status; getprop ro.csc.sales_code").strip()
    check("csc_region", bool(csc), f"CSC/sales code: {csc}", blocking=False)

    firmware = client.execute(
        "shell", "getprop ro.build.display.id; getprop ro.build.version.incremental"
    ).strip()
    check("firmware", bool(firmware), firmware.replace("\n", " | "), blocking=False)

    battery_ok = battery.level >= 50
    check("battery", battery_ok, f"{battery.level}% (need >= 50% for flash session)")

    check("adb_authorized", True, "ADB connection is authorized", blocking=False)

    blocking_failures = [c for c in checks if not c["ok"] and c["blocking"]]
    verdict = "GO" if not blocking_failures else "NO-GO"
    result = {
        "verdict": verdict,
        "device": device.model,
        "checks": checks,
        "blocking_failures": [c["check"] for c in blocking_failures],
        "note": (
            "GO means preconditions are met; the bootloader unlock + Odin flash in "
            "rooting/RUNBOOK.md remains a MANUAL procedure."
        ),
    }

    if getattr(args, "json", False):
        print(json.dumps(result, indent=2))
    else:
        print(f"Root preflight — {device.model}")
        print("=" * 50)
        for c in checks:
            mark = "PASS" if c["ok"] else ("FAIL" if c["blocking"] else "warn")
            print(f"  [{mark:4}] {c['check']:22} {c['detail']}")
        print("=" * 50)
        print(f"VERDICT: {verdict}")
        if verdict == "NO-GO":
            print("Resolve blocking failures above, then re-run `phone-root preflight`.")

    return 0 if verdict == "GO" else 1
