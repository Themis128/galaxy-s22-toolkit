"""Phone File Transfer Skill Implementation."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from phone import AdbClient


def format_size(size: int) -> str:
    """Format bytes to human readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def format_speed(size: int, elapsed: float) -> str:
    """Format transfer speed."""
    if elapsed == 0:
        return "N/A"
    return format_size(int(size / elapsed)) + "/s"


def show_progress(
    current: int, total: int, start_time: float, prefix: str = ""
) -> None:
    """Display transfer progress bar."""
    if total == 0:
        return

    elapsed = time.time() - start_time
    percent = (current / total) * 100
    speed = format_speed(current, elapsed)

    bar_width = 40
    filled = int(bar_width * current / total)
    bar = "█" * filled + "░" * (bar_width - filled)

    sys.stdout.write(
        f"\r{prefix}[{bar}] {percent:.1f}% "
        f"({format_size(current)}/{format_size(total)}) "
        f"{speed}"
    )
    sys.stdout.flush()

    if current >= total:
        sys.stdout.write("\n")
        sys.stdout.flush()


def pull_file(args: argparse.Namespace, client: AdbClient) -> int:
    """Pull file from device to local."""
    try:
        remote_path = args.remote
        local_path = Path(args.local or ".").resolve()

        if local_path.is_dir():
            local_path = local_path / Path(remote_path).name

        # Ensure parent directory exists
        local_path.parent.mkdir(parents=True, exist_ok=True)

        # Get file size first
        stat_result = client.execute("shell", "stat", "-c", "%s", remote_path)
        try:
            total_size = int(stat_result.strip())
        except ValueError:
            total_size = 0

        print(f"Pulling: {remote_path} -> {local_path}")
        if total_size:
            print(f"Size: {format_size(total_size)}")

        start_time = time.time()

        client.pull(remote_path, str(local_path))

        elapsed = time.time() - start_time
        if total_size:
            print(f"Done in {elapsed:.1f}s ({format_speed(total_size, elapsed)})")
        else:
            print("Done")

        return 0
    except Exception as e:
        print(f"Error pulling file: {e}", file=sys.stderr)
        return 1


def push_file(args: argparse.Namespace, client: AdbClient) -> int:
    """Push file from local to device."""
    try:
        local_path = Path(args.local).resolve()
        remote_path = args.remote

        if not local_path.exists():
            print(f"Error: Local file not found: {local_path}", file=sys.stderr)
            return 1

        total_size = local_path.stat().st_size
        print(f"Pushing: {local_path} -> {remote_path}")
        print(f"Size: {format_size(total_size)}")

        start_time = time.time()

        def progress_callback(current: int, total: int) -> None:
            show_progress(current, total, start_time, "Push: ")

        client.push(str(local_path), remote_path, callback=progress_callback)

        elapsed = time.time() - start_time
        print(f"Done in {elapsed:.1f}s ({format_speed(total_size, elapsed)})")

        return 0
    except Exception as e:
        print(f"Error pushing file: {e}", file=sys.stderr)
        return 1


def list_files(args: argparse.Namespace, client: AdbClient) -> int:
    """List files on device."""
    try:
        remote_path = args.remote or "/sdcard"
        result = client.execute("shell", "ls", "-la", remote_path)

        if args.json:
            import json

            lines = result.strip().split("\n")
            files = []
            for line in lines:
                if line and not line.startswith("total"):
                    parts = line.split()
                    if len(parts) >= 9:
                        files.append(
                            {
                                "permissions": parts[0],
                                "links": parts[1],
                                "owner": parts[2],
                                "group": parts[3],
                                "size": int(parts[4]),
                                "month": parts[5],
                                "day": parts[6],
                                "time": parts[7],
                                "name": " ".join(parts[8:]),
                            }
                        )
            print(json.dumps(files, indent=2))
        else:
            print(result)

        return 0
    except Exception as e:
        print(f"Error listing files: {e}", file=sys.stderr)
        return 1


def delete_file(args: argparse.Namespace, client: AdbClient) -> int:
    """Delete file on device."""
    try:
        remote_path = args.remote
        if not args.force:
            confirm = input(f"Delete {remote_path}? (y/N): ")
            if confirm.lower() != "y":
                print("Cancelled")
                return 0

        client.execute("shell", "rm", "-f", remote_path)
        print(f"Deleted: {remote_path}")
        return 0
    except Exception as e:
        print(f"Error deleting file: {e}", file=sys.stderr)
        return 1


def mkdir_remote(args: argparse.Namespace, client: AdbClient) -> int:
    """Create directory on device."""
    try:
        remote_path = args.remote
        client.execute("shell", "mkdir", "-p", remote_path)
        print(f"Created directory: {remote_path}")
        return 0
    except Exception as e:
        print(f"Error creating directory: {e}", file=sys.stderr)
        return 1


def main() -> None:
    # Set MSYS_NO_PATHCONV=1 to prevent MSYS/Git Bash path conversion
    # (e.g. /sdcard/... -> C:/Program Files/Git/sdcard/...)
    os.environ["MSYS_NO_PATHCONV"] = "1"

    parser = argparse.ArgumentParser(description="Phone File Transfer")
    parser.add_argument("--serial", help="Device serial")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Pull command
    pull_parser = subparsers.add_parser("pull", help="Pull file from device")
    pull_parser.add_argument("remote", help="Remote path on device")
    pull_parser.add_argument("local", nargs="?", help="Local destination path")
    pull_parser.set_defaults(func=pull_file)

    # Push command
    push_parser = subparsers.add_parser("push", help="Push file to device")
    push_parser.add_argument("local", help="Local file path")
    push_parser.add_argument("remote", help="Remote destination path on device")
    push_parser.set_defaults(func=push_file)

    # List command
    list_parser = subparsers.add_parser("list", help="List files on device")
    list_parser.add_argument("remote", nargs="?", help="Remote path (default: /sdcard)")
    list_parser.add_argument("--json", action="store_true", help="JSON output")
    list_parser.set_defaults(func=list_files)

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete file on device")
    delete_parser.add_argument("remote", help="Remote path on device")
    delete_parser.add_argument("--force", "-f", action="store_true", help="Force delete")
    delete_parser.set_defaults(func=delete_file)

    # Mkdir command
    mkdir_parser = subparsers.add_parser("mkdir", help="Create directory on device")
    mkdir_parser.add_argument("remote", help="Remote path on device")
    mkdir_parser.set_defaults(func=mkdir_remote)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    client = AdbClient(serial=args.serial) if args.serial else AdbClient()

    if not client.is_connected:
        print("Error: No device connected", file=sys.stderr)
        sys.exit(3)

    try:
        if hasattr(args, "func"):
            sys.exit(args.func(args, client))
        else:
            parser.print_help()
            sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(4)


if __name__ == "__main__":
    main()
