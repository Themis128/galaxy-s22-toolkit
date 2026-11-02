"""Phone Screen Control Skill - Screenshot, screenrecord, UI dump, and input control."""

from __future__ import annotations

import argparse
import json
import sys

from phone.adb import AdbClient
from phone.screen import ScreenModule


def get_client(serial: str | None = None) -> AdbClient:
    """Get ADB client, optionally with specific serial."""
    if serial:
        return AdbClient(serial=serial)
    return AdbClient()


def cmd_screenshot(args: argparse.Namespace) -> int:
    """Take screenshot and pull to local."""
    client = get_client(args.serial)
    screen = ScreenModule(client)

    try:
        local_file = screen.screenshot_pull(
            local_path=args.output,
            filename=args.filename,
        )
        if args.json:
            print(json.dumps({"success": True, "file": local_file}))
        else:
            print(f"Screenshot saved to: {local_file}")
        return 0
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_record(args: argparse.Namespace) -> int:
    """Record screen and pull to local."""
    client = get_client(args.serial)
    screen = ScreenModule(client)

    try:
        local_file = screen.record_and_pull(
            local_path=args.output,
            filename=args.filename,
            time_limit=args.time_limit,
            bit_rate=args.bit_rate,
            size=args.size,
        )
        if args.json:
            print(json.dumps({"success": True, "file": local_file}))
        else:
            print(f"Recording saved to: {local_file}")
        return 0
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_ui_dump(args: argparse.Namespace) -> int:
    """Get UI hierarchy dump."""
    client = get_client(args.serial)
    screen = ScreenModule(client)

    try:
        if args.pull:
            local_file = screen.get_ui_dump_pull(local_path=args.output)
            if args.json:
                print(json.dumps({"success": True, "file": local_file}))
            else:
                print(f"UI dump saved to: {local_file}")
        else:
            dump = screen.get_ui_dump(compressed=args.compressed)
            if args.json:
                print(json.dumps({"success": True, "dump": dump}))
            else:
                print(dump)
        return 0
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_tap(args: argparse.Namespace) -> int:
    """Tap screen coordinates."""
    client = get_client(args.serial)
    screen = ScreenModule(client)

    try:
        result = screen.tap(args.x, args.y)
        if args.json:
            print(json.dumps({"success": True, "output": result}))
        else:
            print(f"Tapped at ({args.x}, {args.y})")
        return 0
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_swipe(args: argparse.Namespace) -> int:
    """Swipe between coordinates."""
    client = get_client(args.serial)
    screen = ScreenModule(client)

    try:
        result = screen.swipe(args.x1, args.y1, args.x2, args.y2, args.duration)
        if args.json:
            print(json.dumps({"success": True, "output": result}))
        else:
            print(f"Swiped from ({args.x1}, {args.y1}) to ({args.x2}, {args.y2})")
        return 0
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_text(args: argparse.Namespace) -> int:
    """Type text into focused field."""
    client = get_client(args.serial)
    screen = ScreenModule(client)

    try:
        result = screen.text(args.text)
        if args.json:
            print(json.dumps({"success": True, "output": result}))
        else:
            print(f"Typed: {args.text}")
        return 0
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_keyevent(args: argparse.Namespace) -> int:
    """Send key event."""
    client = get_client(args.serial)
    screen = ScreenModule(client)

    try:
        result = screen.keyevent(args.key)
        if args.json:
            print(json.dumps({"success": True, "output": result}))
        else:
            print(f"Sent key: {args.key}")
        return 0
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_display_info(args: argparse.Namespace) -> int:
    """Get display information."""
    client = get_client(args.serial)
    screen = ScreenModule(client)

    try:
        info = screen.get_display_info()
        if args.json:
            print(json.dumps({"success": True, "display": info}))
        else:
            print("Display Information:")
            for key, value in info.items():
                print(f"  {key}: {value}")
        return 0
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_orientation(args: argparse.Namespace) -> int:
    """Get or set screen orientation."""
    client = get_client(args.serial)
    screen = ScreenModule(client)

    try:
        if args.set is not None:
            success = screen.set_orientation(args.set)
            if args.json:
                print(json.dumps({"success": success}))
            else:
                print(f"Orientation set to {args.set}" if success else "Failed to set orientation")
            return 0 if success else 1
        else:
            orientation = screen.get_orientation()
            if args.json:
                print(json.dumps({"success": True, "orientation": orientation}))
            else:
                orientations = {0: "default", 1: "landscape", 2: "portrait", 3: "reverse_landscape", 4: "reverse_portrait"}
                name = orientations.get(orientation, str(orientation))
                print(f"Current orientation: {name} ({orientation})")
            return 0
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_density(args: argparse.Namespace) -> int:
    """Get or set screen density."""
    client = get_client(args.serial)
    screen = ScreenModule(client)

    try:
        if args.set is not None:
            success = screen.set_screen_density(args.set)
            if args.json:
                print(json.dumps({"success": success}))
            else:
                print(f"Density set to {args.set} (reboot to persist)" if success else "Failed to set density")
            return 0 if success else 1
        elif args.reset:
            success = screen.reset_screen_density()
            if args.json:
                print(json.dumps({"success": success}))
            else:
                print("Density reset to default" if success else "Failed to reset density")
            return 0 if success else 1
        else:
            density = screen.get_screen_density()
            if args.json:
                print(json.dumps({"success": True, "density": density}))
            else:
                print(f"Current density: {density} DPI")
            return 0
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_bugreport(args: argparse.Namespace) -> int:
    """Take bugreport and pull to local."""
    client = get_client(args.serial)
    screen = ScreenModule(client)

    try:
        local_file = screen.take_bugreport(local_path=args.output)
        if args.json:
            print(json.dumps({"success": True, "file": local_file}))
        else:
            print(f"Bugreport saved to: {local_file}")
        return 0
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_press(args: argparse.Namespace) -> int:
    """Press hardware key."""
    client = get_client(args.serial)
    screen = ScreenModule(client)

    try:
        key_map = {
            "back": screen.press_back,
            "home": screen.press_home,
            "recent": screen.press_recent,
            "power": screen.press_power,
            "volume_up": screen.press_volume_up,
            "volume_down": screen.press_volume_down,
        }
        result = key_map[args.key]()
        if args.json:
            print(json.dumps({"success": True, "output": result}))
        else:
            print(f"Pressed {args.key}")
        return 0
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="phone-screen-control",
        description="Control Android device screen: screenshot, record, UI dump, input",
    )
    parser.add_argument("--serial", "-s", help="Device serial number")
    parser.add_argument("--json", "-j", action="store_true", help="Output JSON")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # screenshot
    sp = subparsers.add_parser("screenshot", help="Take screenshot and pull to local")
    sp.add_argument("-o", "--output", default=".", help="Output directory")
    sp.add_argument("-f", "--filename", help="Output filename")
    sp.set_defaults(func=cmd_screenshot)

    # record
    sp = subparsers.add_parser("record", help="Record screen and pull to local")
    sp.add_argument("-o", "--output", default=".", help="Output directory")
    sp.add_argument("-f", "--filename", help="Output filename")
    sp.add_argument("-t", "--time-limit", type=int, default=180, help="Time limit in seconds (max 180)")
    sp.add_argument("-b", "--bit-rate", type=int, default=4000000, help="Bit rate in bps")
    sp.add_argument("--size", help="Video size (e.g., 1920x1080)")
    sp.set_defaults(func=cmd_record)

    # ui-dump
    sp = subparsers.add_parser("ui-dump", help="Get UI hierarchy dump")
    sp.add_argument("-o", "--output", default=".", help="Output directory (with --pull)")
    sp.add_argument("--pull", action="store_true", help="Pull dump to local file")
    sp.add_argument("--compressed", action="store_true", help="Compressed dump")
    sp.set_defaults(func=cmd_ui_dump)

    # tap
    sp = subparsers.add_parser("tap", help="Tap screen coordinates")
    sp.add_argument("x", type=int, help="X coordinate")
    sp.add_argument("y", type=int, help="Y coordinate")
    sp.set_defaults(func=cmd_tap)

    # swipe
    sp = subparsers.add_parser("swipe", help="Swipe between coordinates")
    sp.add_argument("x1", type=int, help="Start X")
    sp.add_argument("y1", type=int, help="Start Y")
    sp.add_argument("x2", type=int, help="End X")
    sp.add_argument("y2", type=int, help="End Y")
    sp.add_argument("-d", "--duration", type=int, default=300, help="Duration in ms")
    sp.set_defaults(func=cmd_swipe)

    # text
    sp = subparsers.add_parser("text", help="Type text into focused field")
    sp.add_argument("text", help="Text to type")
    sp.set_defaults(func=cmd_text)

    # keyevent
    sp = subparsers.add_parser("keyevent", help="Send key event")
    sp.add_argument("key", help="Key code (e.g., KEYCODE_BACK, 4)")
    sp.set_defaults(func=cmd_keyevent)

    # display-info
    sp = subparsers.add_parser("display-info", help="Get display information")
    sp.set_defaults(func=cmd_display_info)

    # orientation
    sp = subparsers.add_parser("orientation", help="Get or set screen orientation")
    sp.add_argument("--set", type=int, choices=[0, 1, 2, 3, 4], help="Set orientation (0=default, 1=landscape, 2=portrait, 3=reverse landscape, 4=reverse portrait)")
    sp.set_defaults(func=cmd_orientation)

    # density
    sp = subparsers.add_parser("density", help="Get or set screen density")
    sp.add_argument("--set", type=int, help="Set density DPI (reboot to persist)")
    sp.add_argument("--reset", action="store_true", help="Reset to default density")
    sp.set_defaults(func=cmd_density)

    # bugreport
    sp = subparsers.add_parser("bugreport", help="Take bugreport and pull to local")
    sp.add_argument("-o", "--output", default=".", help="Output directory")
    sp.set_defaults(func=cmd_bugreport)

    # press
    sp = subparsers.add_parser("press", help="Press hardware key")
    sp.add_argument("key", choices=["back", "home", "recent", "power", "volume_up", "volume_down"], help="Key to press")
    sp.set_defaults(func=cmd_press)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())