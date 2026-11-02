"""Phone Logcat Skill Implementation."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time

from phone import AdbClient, LogEntry, LogLevel


def format_log_entry(entry: LogEntry, args: argparse.Namespace) -> str:
    """Format a log entry for display."""
    timestamp = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S") if entry.timestamp else "???:???"

    if args.json:
        return json.dumps({
            "timestamp": timestamp,
            "level": entry.level.value if entry.level else "UNKNOWN",
            "tag": entry.tag or "-",
            "pid": entry.pid,
            "tid": entry.tid,
            "message": entry.message,
        })

    # Color mapping
    colors = {
        "V": "\033[37m",  # White
        "D": "\033[36m",  # Cyan
        "I": "\033[32m",  # Green
        "W": "\033[33m",  # Yellow
        "E": "\033[31m",  # Red
        "F": "\033[35m",  # Magenta
    }
    reset = "\033[0m"

    level_char = entry.level.value[0] if entry.level else "V"
    color = colors.get(level_char, "")

    tag = entry.tag or "-"
    tag = tag[:15].rjust(15) if args.pad_tags else tag

    return f"{timestamp} {color}{level_char}{tag}{reset} {entry.message[:200]}"


def filter_logcat(args: argparse.Namespace, client: AdbClient) -> int:
    """Stream logcat with filtering."""
    patterns = [re.compile(p) for p in args.pattern] if args.pattern else None
    levels = []

    if args.level:
        level_map = {
            "V": LogLevel.VERBOSE,
            "D": LogLevel.DEBUG,
            "I": LogLevel.INFO,
            "W": LogLevel.WARN,
            "E": LogLevel.ERROR,
            "F": LogLevel.FATAL,
        }
        for char in args.level.upper():
            if char in level_map:
                levels.append(level_map[char])

    try:
        count = 0

        with client.logcat_stream_iter() as lines:
            for line in lines:
                if args.timeout and count >= args.timeout:
                    break

                if patterns:
                    if not any(p.search(line) for p in patterns):
                        continue

                try:
                    entry = LogEntry.from_line(line)
                    if levels and entry.level not in levels:
                        continue

                    if args.tag and entry.tag and args.tag not in entry.tag:
                        continue

                    print(format_log_entry(entry, args))
                    count += 1

                    if args.count and count >= args.count:
                        return 0
                except Exception:
                    continue

        return 0
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def show_errors(args: argparse.Namespace, client: AdbClient) -> int:
    """Show recent errors/crash reports."""
    try:
        mod = client.logcat_module

        if args.anr:
            anrs = mod.get_anrs(lines=args.count)
            if args.json:
                print(json.dumps([a.model for a in anrs], indent=2, default=str))
            else:
                print(f"ANRs (last {args.count or 'all'}):")
                for anr in anrs:
                    print(f"  - {anr.timestamp}: {anr.message[:100]}")
            return 0

        if args.crashes:
            errors = mod.get_errors(lines=args.count)
            if args.json:
                print(json.dumps([e.model for e in errors], indent=2, default=str))
            else:
                print(f"Errors (last {args.count or 'all'}):")
                for err in errors:
                    print(f"  - [{err.level.value}] {err.tag}: {err.message[:100]}")
            return 0

        # Combined report
        print("Latest errors and crashes:")
        errors = mod.get_errors(lines=args.count or 10)
        anrs = mod.get_anrs(lines=args.count or 10)

        all_events = []
        for e in errors:
            all_events.append(("ERROR", e))
        for a in anrs:
            all_events.append(("ANR", a))

        all_events.sort(key=lambda x: x[1].timestamp or time.strftime("1970-01-01"), reverse=True)

        for event_type, event in all_events[:args.count or 10]:
            print(f"[{event_type}] {event.timestamp}: {event.message[:100]}")

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def export_logs(args: argparse.Namespace, client: AdbClient) -> int:
    """Export logs to file."""
    try:
        output_file = args.output or f"logs_{int(time.time())}.txt"

        if args.past_hours:
            # Get logs from past N hours
            mod = client.logcat_module
            errors = mod.get_errors(lines=args.count or 100)
            anrs = mod.get_anrs(lines=args.count or 100)

            with open(output_file, "w") as f:
                f.write(f"Log export - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 50 + "\n\n")
                f.write("Errors:\n")
                for e in errors:
                    f.write(f"{e.timestamp}: {e.tag}: {e.message}\n")
                f.write("\nANRs:\n")
                for a in anrs:
                    f.write(f"{a.timestamp}: {a.message}\n")
        else:
            # Pull logs via adb
            result = client.execute("logcat", "-d", "-v", "threadtime")
            with open(output_file, "w") as f:
                f.write(result)

        print(f"Logs exported to: {output_file}")
        return 0
    except Exception as e:
        print(f"Error exporting logs: {e}", file=sys.stderr)
        return 1


def clear_logs(args: argparse.Namespace, client: AdbClient) -> int:
    """Clear device logs."""
    try:
        client.execute("shell", "logcat", "-c")
        print("Logs cleared")
        return 0
    except Exception as e:
        print(f"Error clearing logs: {e}", file=sys.stderr)
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Phone Logcat Viewer")
    parser.add_argument("--serial", help="Device serial")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Stream command
    stream_parser = subparsers.add_parser("stream", help="Stream logs")
    stream_parser.add_argument("--pattern", "-p", action="append", help="Filter patterns")
    stream_parser.add_argument("--level", "-l", help="Log levels (V,D,I,W,E,F)")
    stream_parser.add_argument("--tag", "-t", help="Filter by tag")
    stream_parser.add_argument("--count", "-n", type=int, help="Number of lines")
    stream_parser.add_argument("--timeout", type=int, help="Timeout in seconds")
    stream_parser.add_argument("--pad-tags", action="store_true")
    stream_parser.add_argument("--json", action="store_true", help="JSON output")
    stream_parser.set_defaults(func=filter_logcat)

    # Errors command
    errors_parser = subparsers.add_parser("errors", help="Show errors")
    errors_parser.add_argument("--crashes", action="store_true", help="Include crash reports")
    errors_parser.add_argument("--anr", action="store_true", help="Include ANR reports")
    errors_parser.add_argument("--count", "-n", type=int, help="Number to show")
    errors_parser.add_argument("--json", action="store_true")
    errors_parser.set_defaults(func=show_errors)

    # Export command
    export_parser = subparsers.add_parser("export", help="Export logs")
    export_parser.add_argument("--output", "-o", help="Output file")
    export_parser.add_argument("--past-hours", type=int, help="Export logs from past N hours")
    export_parser.add_argument("--count", "-n", type=int, help="Number of events")
    export_parser.set_defaults(func=export_logs)

    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Clear logs")
    clear_parser.set_defaults(func=clear_logs)

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
