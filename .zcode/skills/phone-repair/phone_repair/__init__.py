#!/usr/bin/env python3
"""phone-repair skill CLI: approved repair actions for the connected device."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# <root>/.zcode/skills/phone-repair/phone_repair/__init__.py -> <root>
PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT / "phone-lib" / "src"))

from phone import create_client  # noqa: E402
from phone.repair import RepairModule  # noqa: E402


def _load_repair_config() -> dict:
    try:
        import yaml

        with open(PROJECT_ROOT / "diagnostics" / "config.yaml", encoding="utf-8") as f:
            return (yaml.safe_load(f) or {}).get("repair", {}) or {}
    except Exception:
        return {}


def _history_path() -> str | None:
    rel = _load_repair_config().get("history_file")
    return str(PROJECT_ROOT / rel) if rel else None


def _latest_diagnostics() -> list[dict] | None:
    try:
        import json as _json

        reports = sorted((PROJECT_ROOT / "diagnostics" / "reports").glob("health_report_*.json"))
        if not reports:
            return None
        report = _json.loads(reports[-1].read_text(encoding="utf-8"))
        return report.get("check_results") or report.get("results") or None
    except Exception:
        return None


def _result_json(result) -> dict:
    return {
        "action": result.action.name,
        "success": result.success,
        "message": result.message,
        "details": result.details,
        "duration_ms": round(result.duration_ms, 1),
        "requires_reboot": result.requires_reboot,
    }


def _wireless_settings() -> dict | None:
    try:
        import yaml

        with open(PROJECT_ROOT / "diagnostics" / "config.yaml", encoding="utf-8") as f:
            device_cfg = (yaml.safe_load(f) or {}).get("device", {})
        wireless = device_cfg.get("wireless_adb") or None
        if wireless:
            wireless = {**wireless, "preferred_serial": device_cfg.get("serial")}
        return wireless
    except Exception:
        return None


def _client_or_none():
    client = create_client(wireless=_wireless_settings())
    if not client.is_connected:
        print("No ADB device connected", file=sys.stderr)
        return None
    return client


def main() -> int:
    parser = argparse.ArgumentParser(prog="phone-repair")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="List all available repair actions")
    sub.add_parser("recommend", help="Actions recommended by the latest diagnostics")
    sub.add_parser("history", help="Show persisted repair history")
    run = sub.add_parser("run", help="Execute repair actions (approval policy applies)")
    run.add_argument("actions", nargs="+", help="Action names, or 'auto' for auto-approve only")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 2

    if args.command == "list":
        print(json.dumps([
            {
                "name": a.name,
                "description": a.description,
                "category": a.category,
                "risk_level": a.risk_level,
                "requires_root": a.requires_root,
                "auto_approve": a.auto_approve,
            }
            for a in RepairModule.AVAILABLE_ACTIONS
        ], indent=2))
        return 0

    if args.command == "recommend":
        client = _client_or_none()
        if client is None:
            return 1
        module = RepairModule(client, history_path=_history_path())
        actions = asyncio.run(module.get_pending_actions(_latest_diagnostics()))
        print(json.dumps([{
            "name": a.name,
            "risk_level": a.risk_level,
            "auto_approve": a.auto_approve,
            "requires_root": a.requires_root,
        } for a in actions], indent=2))
        return 0

    if args.command == "run":
        client = _client_or_none()
        if client is None:
            return 1
        names = (
            [a.name for a in RepairModule.AVAILABLE_ACTIONS if a.auto_approve]
            if args.actions == ["auto"]
            else args.actions
        )
        module = RepairModule(client, history_path=_history_path())
        results = asyncio.run(module.execute_multiple(names))
        body = {
            "results": [_result_json(r) for r in results],
            "successful": sum(1 for r in results if r.success),
            "total": len(results),
        }
        print(json.dumps(body, indent=2))
        return 0

    if args.command == "history":
        client = _client_or_none()
        if client is None:
            return 1
        module = RepairModule(client, history_path=_history_path())
        print(json.dumps({
            "history": [_result_json(r) for r in module.history],
            "total": len(module.history),
        }, indent=2))
        return 0

    parser.error(f"Unknown command {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
