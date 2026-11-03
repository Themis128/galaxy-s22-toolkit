"""Phone Diagnostics Skill - Comprehensive health check for Android devices."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

from phone.adb import AdbClient
from phone.battery import BatteryModule
from phone.device import DeviceModule
from phone.logcat import LogcatModule
from phone.network import NetworkModule
from phone.storage import StorageModule
from phone.thermal import ThermalModule


def get_client(serial: str | None = None) -> AdbClient:
    """Get ADB client, optionally with specific serial."""
    if serial:
        return AdbClient(serial=serial)
    return AdbClient()


def run_diagnostics(args: argparse.Namespace) -> int:
    """Run full diagnostic suite and output report."""
    client = get_client(args.serial)

    # Initialize modules
    device = DeviceModule(client)
    battery = BatteryModule(client)
    storage = StorageModule(client)
    logcat = LogcatModule(client)
    network = NetworkModule(client)
    thermal = ThermalModule(client)

    report = {
        "timestamp": datetime.now().isoformat(),
        "device": {},
        "battery": {},
        "storage": {},
        "logcat": {},
        "network": {},
        "thermal": {},
    }

    errors = []

    # Device info
    try:
        if not args.json and not args.quiet:
            print("📱 Gathering device info...")
        info = device.get_device_info()
        report["device"] = {
            "model": info.model,
            "manufacturer": info.manufacturer,
            "android_version": info.android_version,
            "security_patch": info.security_patch,
            "build_number": info.build_number,
            "serial": info.serial,
            "cpu_abi": info.cpu_abi,
            "total_memory": info.total_memory,
        }
    except Exception as e:
        errors.append(f"Device info: {e}")

    # Battery
    try:
        if not args.json and not args.quiet:
            print("🔋 Checking battery...")
        health = battery.get_battery_health()
        report["battery"] = {
            "level": health.level,
            "status": health.status_str,
            "health": health.health_str,
            "technology": health.technology_str,
            "temperature": health.temperature,
            "voltage": health.voltage,
            "capacity": health.capacity,
            "cycle_count": health.cycle_count,
        }
    except Exception as e:
        errors.append(f"Battery: {e}")

    # Storage
    try:
        if not args.json and not args.quiet:
            print("💾 Checking storage...")
        usage = storage.get_storage_usage()
        report["storage"] = {
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "percent_used": round(usage.used / usage.total * 100, 1) if usage.total > 0 else 0,
        }
    except Exception as e:
        errors.append(f"Storage: {e}")

    # Logcat (crashes/ANRs)
    try:
        if not args.json and not args.quiet:
            print("📋 Checking logs for crashes/ANRs...")
        crashes = logcat.find_crashes(since_minutes=args.log_minutes)
        anrs = logcat.find_anrs(since_minutes=args.log_minutes)
        report["logcat"] = {
            "crashes_found": len(crashes),
            "anrs_found": len(anrs),
            "crashes": [{"time": c.timestamp.isoformat(), "package": c.package, "message": c.message[:200]} for c in crashes[:5]],
            "anrs": [{"time": a.timestamp.isoformat(), "package": a.package, "message": a.message[:200]} for a in anrs[:5]],
        }
    except Exception as e:
        errors.append(f"Logcat: {e}")

    # Network
    try:
        if not args.json and not args.quiet:
            print("🌐 Checking network...")
        connectivity = network.check_connectivity()
        dns = network.check_dns()
        wifi = network.get_wifi_info()
        report["network"] = {
            "connectivity": connectivity,
            "dns": dns,
            "wifi": wifi,
        }
    except Exception as e:
        errors.append(f"Network: {e}")

# Thermal
        try:
            if not args.json and not args.quiet:
                print("🌡️ Checking thermal...")
            zones = thermal.get_thermal_zones()
            throttling = thermal.get_throttling_status()
            report["thermal"] = {
                "zones": [{"name": z.name, "temp_c": z.temp_c, "type": z.type} for z in zones],
                "throttling": throttling,
            }
        except Exception as e:
            errors.append(f"Thermal: {e}")

    # Output
    if args.json:
        print(json.dumps({"success": len(errors) == 0, "report": report, "errors": errors}, indent=2))
    else:
        if not args.quiet:
            print("\n" + "=" * 60)
            print(f"DIAGNOSTIC REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 60)

            # Device
            d = report["device"]
            print(f"\n📱 Device: {d.get('manufacturer', 'Unknown')} {d.get('model', 'Unknown')}")
            print(f"   Android: {d.get('android_version', 'Unknown')} | Security Patch: {d.get('security_patch', 'Unknown')}")
            print(f"   Serial: {d.get('serial', 'Unknown')} | CPU: {d.get('cpu_abi', 'Unknown')}")

            # Battery
            b = report["battery"]
            print(f"\n🔋 Battery: {b.get('level', '?')}% | {b.get('status', 'Unknown')} | Health: {b.get('health', 'Unknown')}")
            print(f"   Temp: {b.get('temperature', '?')}°C | Voltage: {b.get('voltage', '?')}mV | Cycles: {b.get('cycle_count', '?')}")

            # Storage
            s = report["storage"]
            print(f"\n💾 Storage: {s.get('percent_used', '?')}% used ({s.get('used', 0)}/{s.get('total', 0)} bytes)")

            # Logcat
            logcat_report = report["logcat"]
            print(f"\n📋 Logs (last {args.log_minutes} min): {logcat_report.get('crashes_found', 0)} crashes, {logcat_report.get('anrs_found', 0)} ANRs")
            if logcat_report.get("crashes_found", 0) > 0:
                for c in logcat_report["crashes"]:
                    print(f"   ⚠️  {c['package']}: {c['message']}")
            if logcat_report.get("anrs_found", 0) > 0:
                for a in logcat_report["anrs"]:
                    print(f"   ⚠️  {a['package']}: {a['message']}")

            # Network
            n = report["network"]
            conn = n.get("connectivity", {})
            print(f"\n🌐 Network: Internet={'✅' if conn.get('internet') else '❌'} | DNS={'✅' if conn.get('dns') else '❌'}")
            if n.get("wifi"):
                w = n["wifi"]
                print(f"   WiFi: {w.get('ssid', 'Unknown')} | Signal: {w.get('rssi', '?')} dBm | Link Speed: {w.get('link_speed', '?')} Mbps")

            # Thermal
            t = report["thermal"]
            print(f"\n🌡️ Thermal: Throttling={'⚠️ YES' if t.get('throttling') else '✅ No'}")
            for zone in t.get("zones", [])[:3]:
                print(f"   {zone.get('name', 'Unknown')}: {zone.get('temp', '?')}°C ({zone.get('type', 'Unknown')})")

            if errors:
                print(f"\n⚠️  Errors: {len(errors)}")
                for e in errors:
                    print(f"   - {e}")

            print("\n" + "=" * 60)

    return 0 if len(errors) == 0 else 1


def cmd_device(args: argparse.Namespace) -> int:
    """Show device info only."""
    client = get_client(args.serial)
    device = DeviceModule(client)
    try:
        info = device.get_device_info()
        if args.json:
            print(json.dumps({
                "model": info.model,
                "manufacturer": info.manufacturer,
                "android_version": info.android_version,
                "security_patch": info.security_patch,
                "build_number": info.build_number,
                "serial": info.serial,
                "cpu_abi": info.cpu_abi,
                "total_memory": info.total_memory,
            }, indent=2))
        else:
            print(f"Model: {info.manufacturer} {info.model}")
            print(f"Android: {info.android_version}")
            print(f"Security Patch: {info.security_patch}")
            print(f"Build: {info.build_number}")
            print(f"Serial: {info.serial}")
            print(f"CPU: {info.cpu_abi}")
            print(f"Memory: {info.total_memory}")
        return 0
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_battery(args: argparse.Namespace) -> int:
    """Show battery info only."""
    client = get_client(args.serial)
    battery = BatteryModule(client)
    try:
        health = battery.get_battery_health()
        if args.json:
            print(json.dumps({
                "level": health.level,
                "status": health.status,
                "health": health.health,
                "technology": health.technology,
                "temperature": health.temperature,
                "voltage": health.voltage,
                "capacity": health.capacity,
                "cycle_count": health.cycle_count,
            }, indent=2))
        else:
            print(f"Level: {health.level}%")
            print(f"Status: {health.status}")
            print(f"Health: {health.health}")
            print(f"Technology: {health.technology}")
            print(f"Temperature: {health.temperature}°C")
            print(f"Voltage: {health.voltage} mV")
            print(f"Capacity: {health.capacity} mAh")
            print(f"Cycle Count: {health.cycle_count}")
        return 0
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_storage(args: argparse.Namespace) -> int:
    """Show storage info only."""
    client = get_client(args.serial)
    storage = StorageModule(client)
    try:
        usage = storage.get_storage_usage()
        if args.json:
            print(json.dumps({
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent_used": round(usage.used / usage.total * 100, 1) if usage.total > 0 else 0,
            }, indent=2))
        else:
            print(f"Total: {usage.total} bytes")
            print(f"Used: {usage.used} bytes ({round(usage.used / usage.total * 100, 1)}%)")
            print(f"Free: {usage.free} bytes")
        return 0
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_logs(args: argparse.Namespace) -> int:
    """Show logcat crashes/ANRs only."""
    client = get_client(args.serial)
    logcat = LogcatModule(client)
    try:
        crashes = logcat.find_crashes(since_minutes=args.minutes)
        anrs = logcat.find_anrs(since_minutes=args.minutes)
        if args.json:
            print(json.dumps({
                "crashes_found": len(crashes),
                "anrs_found": len(anrs),
                "crashes": [{"time": c.timestamp.isoformat(), "package": c.package, "message": c.message} for c in crashes],
                "anrs": [{"time": a.timestamp.isoformat(), "package": a.package, "message": a.message} for a in anrs],
            }, indent=2))
        else:
            print(f"Crashes (last {args.minutes} min): {len(crashes)}")
            for c in crashes:
                print(f"  {c.timestamp} | {c.package} | {c.message[:200]}")
            print(f"ANRs (last {args.minutes} min): {len(anrs)}")
            for a in anrs:
                print(f"  {a.timestamp} | {a.package} | {a.message[:200]}")
        return 0
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_network(args: argparse.Namespace) -> int:
    """Show network info only."""
    client = get_client(args.serial)
    network = NetworkModule(client)
    try:
        connectivity = network.check_connectivity()
        dns = network.check_dns()
        wifi = network.get_wifi_info()
        if args.json:
            print(json.dumps({"connectivity": connectivity, "dns": dns, "wifi": wifi}, indent=2))
        else:
            print(f"Internet: {'✅' if connectivity.get('internet') else '❌'}")
            print(f"DNS: {'✅' if connectivity.get('dns') else '❌'}")
            if wifi:
                print(f"WiFi SSID: {wifi.get('ssid', 'Unknown')}")
                print(f"Signal: {wifi.get('rssi', '?')} dBm")
                print(f"Link Speed: {wifi.get('link_speed', '?')} Mbps")
        return 0
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_thermal(args: argparse.Namespace) -> int:
    """Show thermal info only."""
    client = get_client(args.serial)
    thermal = ThermalModule(client)
    try:
        zones = thermal.get_thermal_zones()
        throttling = thermal.get_throttling_status()
        if args.json:
            print(json.dumps({"zones": [{"name": z.name, "temp_c": z.temp_c, "type": z.type} for z in zones], "throttling": throttling}, indent=2))
        else:
            print(f"Throttling: {'⚠️ YES' if throttling else '✅ No'}")
            for zone in zones:
                print(f"  {zone.name}: {zone.temp_c}°C ({zone.type})")
        return 0
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="phone-diagnostics",
        description="Comprehensive Android device health diagnostics",
    )
    parser.add_argument("--serial", "-s", help="Device serial number")
    parser.add_argument("--json", "-j", action="store_true", help="Output JSON")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress progress output (with --json)")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # run - full diagnostic suite
    sp = subparsers.add_parser("run", help="Run full diagnostic suite")
    sp.add_argument("--log-minutes", type=int, default=60, help="Minutes of logs to check for crashes/ANRs")
    sp.set_defaults(func=run_diagnostics)

    # device
    sp = subparsers.add_parser("device", help="Show device info")
    sp.set_defaults(func=cmd_device)

    # battery
    sp = subparsers.add_parser("battery", help="Show battery health")
    sp.set_defaults(func=cmd_battery)

    # storage
    sp = subparsers.add_parser("storage", help="Show storage usage")
    sp.set_defaults(func=cmd_storage)

    # logs
    sp = subparsers.add_parser("logs", help="Show crashes/ANRs from logcat")
    sp.add_argument("-m", "--minutes", type=int, default=60, help="Minutes of logs to check")
    sp.set_defaults(func=cmd_logs)

    # network
    sp = subparsers.add_parser("network", help="Show network connectivity")
    sp.set_defaults(func=cmd_network)

    # thermal
    sp = subparsers.add_parser("thermal", help="Show thermal status")
    sp.set_defaults(func=cmd_thermal)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
