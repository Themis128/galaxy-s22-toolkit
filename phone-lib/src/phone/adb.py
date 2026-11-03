"""Core ADB connection and command execution."""

from __future__ import annotations

import asyncio
import os
import shlex
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .exceptions import (
    AdbConnectionError,
    CommandFailedError,
    DeviceNotFoundError,
    DeviceUnauthorizedError,
    PhoneError,
    TimeoutError,
)
from .models import LogEntry

if TYPE_CHECKING:
    from .logcat import LogcatModule


class AdbClient:
    """Async ADB client with retry logic and typed responses."""

    DEFAULT_ADB_PATHS = [
        r"C:\Users\tbaltzakis\Android\Sdk\platform-tools\adb.exe",
        "/mnt/c/Users/tbaltzakis/Android/Sdk/platform-tools/adb",
        os.path.expanduser("~/Android/Sdk/platform-tools/adb"),
        "/c/Users/tbaltzakis/Android/Sdk/platform-tools/adb",
        "adb",  # Fallback to PATH
    ]

    def __init__(
        self,
        serial: str | None = None,
        adb_path: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        """
        Initialize ADB client.

        Args:
            serial: Device serial number (auto-detects if None)
            adb_path: Path to adb executable (auto-detects if None)
            timeout: Command timeout in seconds
            max_retries: Max retry attempts for transient failures
            retry_delay: Base delay between retries (exponential backoff)
        """
        self.serial = serial
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._adb_path = adb_path or self._find_adb()
        self._connected_serial: str | None = None
        self._logcat_module: LogcatModule | None = None

    @property
    def logcat_module(self):
        """Get LogcatModule instance."""
        if self._logcat_module is None:
            from .logcat import LogcatModule
            self._logcat_module = LogcatModule(self)
        return self._logcat_module

    @property
    def apps(self):
        """Get AppsModule instance."""
        if not hasattr(self, '_apps_module') or self._apps_module is None:
            from .apps import AppsModule
            self._apps_module = AppsModule(self)
        return self._apps_module

    @property
    def root(self):
        """Get RootModule instance."""
        if not hasattr(self, '_root_module') or self._root_module is None:
            from .root import RootModule
            self._root_module = RootModule(self)
        return self._root_module

    @property
    def device(self):
        """Get DeviceModule instance."""
        if not hasattr(self, '_device_module') or self._device_module is None:
            from .device import DeviceModule
            self._device_module = DeviceModule(self)
        return self._device_module

    @property
    def battery(self):
        """Get BatteryModule instance."""
        if not hasattr(self, '_battery_module') or self._battery_module is None:
            from .battery import BatteryModule
            self._battery_module = BatteryModule(self)
        return self._battery_module

    @property
    def storage(self):
        """Get StorageModule instance."""
        if not hasattr(self, '_storage_module') or self._storage_module is None:
            from .storage import StorageModule
            self._storage_module = StorageModule(self)
        return self._storage_module

    @property
    def network(self):
        """Get NetworkModule instance."""
        if not hasattr(self, '_network_module') or self._network_module is None:
            from .network import NetworkModule
            self._network_module = NetworkModule(self)
        return self._network_module

    @property
    def thermal(self):
        """Get ThermalModule instance."""
        if not hasattr(self, '_thermal_module') or self._thermal_module is None:
            from .thermal import ThermalModule
            self._thermal_module = ThermalModule(self)
        return self._thermal_module

    @property
    def screen(self):
        """Get ScreenModule instance."""
        if not hasattr(self, '_screen_module') or self._screen_module is None:
            from .screen import ScreenModule
            self._screen_module = ScreenModule(self)
        return self._screen_module

    def _find_adb(self) -> str:
        """Find ADB executable in common locations."""
        for path in self.DEFAULT_ADB_PATHS:
            expanded = os.path.expandvars(os.path.expanduser(path))
            if Path(expanded).exists() or path == "adb":
                return expanded
        raise AdbConnectionError(
            "ADB not found. Install Android SDK platform-tools or add adb to PATH.",
            adb_path=None,
        )

    @property
    def adb_path(self) -> str:
        return self._adb_path

    def _base_cmd(self) -> list[str]:
        """Base ADB command with serial if specified."""
        cmd = [self._adb_path]
        if self.serial:
            cmd.extend(["-s", self.serial])
        return cmd

    def _run(
        self,
        args: list[str],
        *,
        capture: bool = True,
        check: bool = True,
        timeout: float | None = None,
        input_data: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run ADB command with retry logic."""
        cmd = self._base_cmd() + args
        last_error: Exception | None = None

        # Set MSYS_NO_PATHCONV=1 to prevent MSYS path conversion on Windows
        env = os.environ.copy()
        env["MSYS_NO_PATHCONV"] = "1"

        for attempt in range(self.max_retries + 1):
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=capture,
                    text=True,
                    timeout=timeout or self.timeout,
                    input=input_data,
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                )
                if check and result.returncode != 0:
                    raise CommandFailedError(
                        command=cmd,
                        exit_code=result.returncode,
                        stdout=result.stdout,
                        stderr=result.stderr,
                    )
                return result
            except subprocess.TimeoutExpired as e:
                last_error = TimeoutError(" ".join(cmd), timeout or self.timeout)
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay * (2 ** attempt))
                    continue
                raise last_error from e
            except CommandFailedError:
                raise
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay * (2 ** attempt))
                    continue
                raise

        raise last_error or PhoneError("Unknown error")

    async def _run_async(
        self,
        args: list[str],
        *,
        capture: bool = True,
        check: bool = True,
        timeout: float | None = None,
        input_data: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run ADB command asynchronously with retry logic."""
        cmd = self._base_cmd() + args
        last_error: Exception | None = None

        # Set MSYS_NO_PATHCONV=1 to prevent MSYS path conversion on Windows
        env = os.environ.copy()
        env["MSYS_NO_PATHCONV"] = "1"

        for attempt in range(self.max_retries + 1):
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE if capture else None,
                    stderr=asyncio.subprocess.PIPE if capture else None,
                    stdin=asyncio.subprocess.PIPE if input_data else None,
                    env=env,
                )
                try:
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(input_data.encode() if input_data else None),
                        timeout=timeout or self.timeout,
                    )
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                    raise TimeoutError(" ".join(cmd), timeout or self.timeout) from None

                stdout_str = stdout.decode("utf-8", errors="replace") if stdout else ""
                stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""

                if check and proc.returncode != 0:
                    raise CommandFailedError(
                        command=cmd,
                        exit_code=proc.returncode or -1,
                        stdout=stdout_str,
                        stderr=stderr_str,
                    )

                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=proc.returncode or 0,
                    stdout=stdout_str,
                    stderr=stderr_str,
                )
            except (CommandFailedError, TimeoutError):
                raise
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
                    continue
                raise

        raise last_error or PhoneError("Unknown error")

    def execute(
        self,
        *args: str,
        capture: bool = True,
        check: bool = True,
        timeout: float | None = None,
    ) -> str:
        """Execute ADB command and return stdout."""
        result = self._run(list(args), capture=capture, check=check, timeout=timeout)
        return result.stdout.strip()

    async def execute_async(
        self,
        *args: str,
        capture: bool = True,
        check: bool = True,
        timeout: float | None = None,
    ) -> str:
        """Execute ADB command asynchronously and return stdout."""
        result = await self._run_async(list(args), capture=capture, check=check, timeout=timeout)
        return result.stdout.strip()

    def execute_raw(
        self,
        *args: str,
        capture: bool = True,
        check: bool = True,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Execute ADB command and return full result."""
        return self._run(list(args), capture=capture, check=check, timeout=timeout)

    # Device management
    def list_devices(self) -> list[dict[str, str]]:
        """List connected devices with details."""
        output = self.execute("devices", "-l")
        devices = []
        for line in output.strip().split("\n")[1:]:  # Skip header
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            device = {
                "serial": parts[0],
                "state": parts[1],
            }
            # Parse key:value pairs
            for part in parts[2:]:
                if ":" in part:
                    k, v = part.split(":", 1)
                    device[k] = v
            devices.append(device)
        return devices

    def get_serial(self) -> str:
        """Get connected device serial, auto-detecting if needed."""
        if self.serial:
            return self.serial

        devices = self.list_devices()
        authorized = [d for d in devices if d.get("state") == "device"]
        if not authorized:
            unauthorized = [d for d in devices if d.get("state") == "unauthorized"]
            if unauthorized:
                raise DeviceUnauthorizedError(unauthorized[0]["serial"])
            raise DeviceNotFoundError(message="No authorized devices found")

        if len(authorized) > 1:
            raise PhoneError(
                f"Multiple devices found: {[d['serial'] for d in authorized]}. Specify serial."
            )

        self._connected_serial = authorized[0]["serial"]
        return self._connected_serial

    def wait_for_device(self, state: str = "device", timeout: float = 30.0) -> str:
        """Wait for device to reach specified state."""
        self.execute("wait-for-" + state, timeout=timeout)
        return self.get_serial()

    def kill_server(self) -> None:
        """Kill ADB server."""
        subprocess.run([self._adb_path, "kill-server"], capture_output=True)

    def start_server(self) -> None:
        """Start ADB server."""
        self.execute("start-server", check=False)

    # Shell commands
    def shell(self, command: str, *, timeout: float | None = None) -> str:
        """Execute shell command on device."""
        return self.execute("shell", command, timeout=timeout)

    async def shell_async(self, command: str, *, timeout: float | None = None) -> str:
        """Execute shell command on device asynchronously."""
        return await self.execute_async("shell", command, timeout=timeout)

    def shell_interactive(self, command: str) -> subprocess.Popen[str]:
        """Start interactive shell command (returns Popen for streaming)."""
        cmd = self._base_cmd() + ["shell", command]
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    # File transfer
    def push(self, local: str, remote: str, *, timeout: float | None = None) -> str:
        """Push file to device."""
        return self.execute("push", local, remote, timeout=timeout or 120.0)

    def pull(self, remote: str, local: str = ".", *, timeout: float | None = None) -> str:
        """Pull file from device."""
        return self.execute("pull", remote, local, timeout=timeout or 120.0)

    def sync(self, local_dir: str, remote_dir: str = "/sdcard/", *, timeout: float | None = None) -> str:
        """Sync directory to device."""
        return self.execute("sync", local_dir, remote_dir, timeout=timeout or 300.0)

    # Screen capture
    def screenshot(self, remote_path: str = "/sdcard/screenshot.png") -> str:
        """Take screenshot and return remote path."""
        self.execute("shell", "screencap", "-p", remote_path)
        return remote_path

    def screenshot_pull(self, local_path: str = ".", remote_path: str = "/sdcard/screenshot.png") -> str:
        """Take screenshot and pull to local."""
        self.screenshot(remote_path)
        self.pull(remote_path, local_path)
        self.execute("shell", "rm", remote_path)
        return local_path

    def screenrecord(
        self,
        remote_path: str = "/sdcard/record.mp4",
        time_limit: int = 180,
        bit_rate: int = 4000000,
    ) -> str:
        """Start screen recording (returns immediately, use pull_recording to get file)."""
        self.execute(
            "shell",
            "screenrecord",
            f"--time-limit={time_limit}",
            f"--bit-rate={bit_rate}",
            remote_path,
        )
        return remote_path

    def pull_recording(self, remote_path: str, local_path: str = ".") -> str:
        """Pull screen recording and clean up remote."""
        self.pull(remote_path, local_path)
        self.execute("shell", "rm", remote_path)
        return local_path

    # Port forwarding
    def forward(self, local_port: int, remote_port: int) -> str:
        """Forward local port to device port."""
        return self.execute("forward", f"tcp:{local_port}", f"tcp:{remote_port}")

    def forward_remove(self, local_port: int) -> str:
        """Remove port forward."""
        return self.execute("forward", "--remove", f"tcp:{local_port}")

    def forward_list(self) -> list[dict[str, str]]:
        """List port forwards."""
        output = self.execute("forward", "--list")
        forwards = []
        for line in output.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 3:
                forwards.append({"local": parts[0], "remote": parts[1], "type": parts[2]})
        return forwards

    def reverse(self, remote_port: int, local_port: int) -> str:
        """Reverse forward: device port to local port."""
        return self.execute("reverse", f"tcp:{remote_port}", f"tcp:{local_port}")

    # Input
    def tap(self, x: int, y: int) -> str:
        """Tap screen coordinates."""
        return self.execute("shell", "input", "tap", str(x), str(y))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> str:
        """Swipe between coordinates."""
        return self.execute("shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration))

    def text(self, text: str) -> str:
        """Type text (escapes spaces)."""
        escaped = text.replace(" ", "%s")
        return self.execute("shell", "input", "text", escaped)

    def keyevent(self, keycode: str | int) -> str:
        """Send key event."""
        return self.execute("shell", "input", "keyevent", str(keycode))

    # Logcat
    def logcat(
        self,
        *filters: str,
        format: str = "threadtime",
        lines: int = 0,
        pid: int | None = None,
        clear: bool = False,
    ) -> list[LogEntry]:
        """Get logcat entries as parsed LogEntry objects."""
        args = ["logcat"]
        if clear:
            args.extend(["-c"])
            self.execute(*args)
            return []

        args.extend(["-v", format])
        if lines > 0:
            args.extend(["-t", str(lines)])
        if pid:
            args.extend([f"--pid={pid}"])
        if filters:
            args.extend(filters)
        else:
            args.append("*:V")

        output = self.execute(*args)
        return self._parse_logcat(output, format)

    def logcat_stream(
        self,
        *filters: str,
        format: str = "threadtime",
        pid: int | None = None,
        callback: Callable[[LogEntry], None] | None = None,
    ) -> None:
        """Stream logcat entries in real-time."""
        args = ["logcat", "-v", format]
        if pid:
            args.extend([f"--pid={pid}"])
        if filters:
            args.extend(filters)
        else:
            args.append("*:V")

        proc = self.shell_interactive(" ".join(shlex.quote(a) for a in args))
        try:
            for line in iter(proc.stdout.readline, ""):
                if not line:
                    break
                entries = self._parse_logcat(line, format)
                for entry in entries:
                    if callback:
                        callback(entry)
        finally:
            proc.terminate()

    def logcat_stream_iter(
        self,
        *filters: str,
        format: str = "threadtime",
        pid: int | None = None,
    ):
        """Stream logcat lines as a context manager for iteration.

        Usage:
            with client.logcat_stream_iter() as lines:
                for line in lines:
                    print(line)
        """
        class LogStream:
            def __init__(self, client, filters, format, pid):
                self.client = client
                self.filters = filters
                self.format = format
                self.pid = pid
                self.proc = None

            def __enter__(self):
                args = ["logcat", "-v", format]
                if pid:
                    args.extend([f"--pid={pid}"])
                if filters:
                    args.extend(filters)
                else:
                    args.append("*:V")

                self.proc = self.client.shell_interactive(" ".join(shlex.quote(a) for a in args))
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                if self.proc:
                    self.proc.terminate()

            def __iter__(self):
                return self

            def __next__(self):
                line = self.proc.stdout.readline()
                if not line:
                    raise StopIteration
                return line.rstrip('\n')

        return LogStream(self, filters, format, pid)

    def _parse_logcat(self, output: str, format: str) -> list[LogEntry]:
        """Parse logcat output based on format."""
        entries = []
        for line in output.strip().split("\n"):
            if not line.strip():
                continue
            if format == "brief":
                entry = LogEntry.parse_brief(line)
            elif format in ("threadtime", "time"):
                entry = LogEntry.parse_threadtime(line)
            else:
                continue
            if entry:
                entries.append(entry)
        return entries

    # Convenience properties
    @property
    def is_connected(self) -> bool:
        """Check if device is connected and authorized."""
        try:
            self.get_serial()
            return True
        except (DeviceNotFoundError, DeviceUnauthorizedError):
            return False

    def __enter__(self) -> AdbClient:
        self.get_serial()
        return self

    def __exit__(self, *args: Any) -> None:
        pass


def create_client(serial: str | None = None, **kwargs: Any) -> AdbClient:
    """Factory function to create AdbClient with defaults for Galaxy S22+."""
    return AdbClient(serial=serial or "RFCTA0AEKZP", **kwargs)
