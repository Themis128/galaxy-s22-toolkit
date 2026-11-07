#!/usr/bin/env python3
"""Device verification report — the honest, local Wondershare Phone Verification.

Produces a resale-style health report (JSON + HTML) for the attached device:
per-category verdicts and a 0-100 validity score, computed from the same
probes the diagnostics runner uses (no cloud, no marketing).

Usage:
    python tools/verify_device.py              # write reports/verification-<ts>.{json,html}
    python tools/verify_device.py --serial S
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
REPORTS = REPO / "reports"
sys.path.insert(0, str(REPO))

try:
    from phone import create_client
except ImportError:  # pragma: no cover
    create_client = None  # type: ignore[assignment]


def _patch_age_days(serial: str | None) -> int | None:
    try:
        import yaml

        with open(REPO / "diagnostics" / "config.yaml", encoding="utf-8") as f:
            device_cfg = (yaml.safe_load(f) or {}).get("device", {})
        wireless = device_cfg.get("wireless_adb") or None
        if wireless:
            wireless = {**wireless, "preferred_serial": device_cfg.get("serial")}
        client = create_client(serial, wireless=wireless)
        patch = client.device.get_security_patch()
        from datetime import date

        return (date.today() - datetime.strptime(patch[:10], "%Y-%m-%d").date()).days
    except Exception:  # noqa: BLE001 - patch age is best-effort
        return None


def _crash_counts(serial: str | None) -> tuple[int, int]:
    try:
        client = create_client(serial)
        logcat = client.logcat_module
        return len(logcat.find_crashes()), len(logcat.find_anrs())
    except Exception:  # noqa: BLE001
        return 0, 0


def collect(serial: str | None = None) -> dict[str, Any]:
    """Gather every category from the live device (single pass)."""
    import yaml

    with open(REPO / "diagnostics" / "config.yaml", encoding="utf-8") as f:
        device_cfg = (yaml.safe_load(f) or {}).get("device", {})
    wireless = device_cfg.get("wireless_adb") or None
    if wireless:
        wireless = {**wireless, "preferred_serial": device_cfg.get("serial")}
    client = create_client(serial, wireless=wireless)

    device = client.device.get_device_info()
    profile = None
    try:
        from phone.capabilities import detect_profile

        profile = detect_profile(client.device)
    except Exception:  # noqa: BLE001
        pass
    battery = client.battery.get_battery_info()
    storage = client.storage.get_storage_info()
    thermal = client.thermal.get_thermal_info()
    network = client.network.get_network_info()
    mem = client.device.get_memory_info()
    data_part = next((p for p in storage if p.mount_point == "/data"), None)
    crashes, anrs = _crash_counts(serial)
    patch_days = _patch_age_days(serial)

    categories: dict[str, dict[str, Any]] = {}

    def score(cat: str, value: int, verdict: str, detail: str) -> None:
        categories[cat] = {"score": value, "verdict": verdict, "detail": detail}

    # Battery (20)
    b = (
        20
        if battery.health.value == "Good" and battery.level > 50
        else (15 if battery.health.value == "Good" else 6)
    )
    score(
        "battery",
        b,
        "OK" if b >= 15 else "WATCH",
        f"{battery.level}% · health {battery.health.value} · {battery.temperature_c:.1f}°C",
    )
    # Storage /data (20)
    if data_part is not None:
        u = data_part.usage_percent
        s = 20 if u < 70 else (12 if u < 85 else 5)
        score(
            "storage",
            s,
            "OK" if u < 85 else "WATCH",
            f"/data {u:.1f}% used ({data_part.free_gb:.0f} GB free)",
        )
    else:
        score("storage", 0, "UNKNOWN", "/data partition not found")
    # Thermal (15)
    thermal_ok = str(thermal.status.value).lower() == "normal" and not thermal.cpu_throttled
    score(
        "thermal",
        15 if thermal_ok else 6,
        "OK" if thermal_ok else "WATCH",
        f"{thermal.status.value}, throttling={thermal.cpu_throttled}",
    )
    # Security (20)
    if patch_days is None:
        score("security", 0, "UNKNOWN", "patch age unavailable")
    else:
        sec = 20 if patch_days < 90 else (12 if patch_days <= 180 else 5)
        score(
            "security",
            sec,
            "OK" if patch_days < 90 else "WATCH" if patch_days <= 180 else "ACT",
            f"patch {patch_days} days old",
        )
    # Stability (10)
    st = 10 if crashes == 0 and anrs == 0 else (6 if crashes + anrs <= 5 else 0)
    score(
        "stability",
        st,
        "OK" if st >= 10 else "WATCH",
        f"{crashes} crashes, {anrs} ANRs (recent buffers)",
    )
    # Memory (10)
    mem_pct = round(
        (int(mem.get("MemTotal", 0)) - int(mem.get("MemAvailable", mem.get("MemFree", 0))))
        / max(int(mem.get("MemTotal", 1)), 1)
        * 100,
        1,
    )
    score("memory", 5 if mem_pct < 80 else 2, "OK" if mem_pct < 80 else "WATCH", f"{mem_pct}% used")
    # Identity (10) — profile resolution quality
    prof_name = profile.marketing_name if profile else "unknown"
    score(
        "identity",
        10 if prof_name not in ("unknown", "") else 5,
        "OK",
        f"{prof_name} ({device.model})",
    )

    total = sum(c["score"] for c in categories.values())
    return {
        "generated": datetime.now().isoformat(),
        "device": {
            "model": device.model,
            "android": device.android_version,
            "api_level": device.api_level,
            "security_patch": device.security_patch,
            "marketing_name": prof_name,
        },
        "score": total,
        "verdict": "GOOD" if total >= 80 else ("FAIR" if total >= 55 else "POOR"),
        "categories": categories,
        "network": {
            "wifi": network.wifi_ssid,
            "signal_dbm": network.wifi_signal_dbm,
            "internet": network.internet_reachable,
        },
    }


_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>Device Verification</title>
<style>body{{font-family:system-ui;margin:2rem;background:#0f1b33;color:#eee}}
.card{{max-width:640px;margin:auto;background:#16264a;border-radius:12px;padding:1.5rem}}
.score{{font-size:3rem;font-weight:700}} .ok{{color:#2ecc71}} .watch{{color:#f39c12}} .act{{color:#e74c3c}}
.row{{display:flex;justify-content:space-between;padding:.45rem 0;border-top:1px solid rgba(255,255,255,.08)}}
</style></head><body><div class="card">
<h1>📱 {model}</h1><div class="score {vclass}">{score} / 100 — {verdict}</div>
{rows}
<p style="opacity:.6;font-size:.8rem">Generated {generated} · Galaxy S22+ Toolkit · local verification, no cloud</p>
</div></body></html>"""


def render_html(report: dict[str, Any]) -> str:
    rows = "".join(
        f'<div class="row"><span>{name.title()}</span>'
        f'<span class="{"ok" if c["verdict"] == "OK" else "watch" if c["verdict"] == "WATCH" else "act"}">'
        f"{c['score']} pts · {c['detail']}</span></div>"
        for name, c in report["categories"].items()
    )
    v = report["verdict"]
    return _HTML.format(
        model=report["device"]["marketing_name"] + " (" + report["device"]["model"] + ")",
        score=report["score"],
        verdict=v,
        vclass="ok" if v == "GOOD" else "watch" if v == "FAIR" else "act",
        rows=rows,
        generated=report["generated"],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--serial")
    args = parser.parse_args(argv)
    if create_client is None:
        print("phone-lib not importable")
        return 1
    report = collect(args.serial)
    REPORTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = REPORTS / f"verification-{stamp}.json"
    html_path = REPORTS / f"verification-{stamp}.html"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    html_path.write_text(render_html(report), encoding="utf-8")
    print(f"score {report['score']}/100 — {report['verdict']}")
    for name, c in report["categories"].items():
        print(f"  {name:10s} {c['score']:3d}  {c['detail']}")
    print(f"report: {json_path}")
    print(f"html  : {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
