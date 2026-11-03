"""Logcat streaming, filtering, and crash/ANR detection."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .adb import AdbClient
from .models import LogEntry, LogLevel


@dataclass
class FilterConfig:
    """Configuration for false positive filtering."""
    # Samsung system tags that commonly produce verbose ERROR/WARN logs
    samsung_tag_patterns: list[str] = field(default_factory=lambda: [
        r"^Samsung.*",
        r"^SEC.*",
        r"^OneUI.*",
        r"^TouchWiz.*",
        r"^SamsungKeyboard.*",
        r"^SamsungIME.*",
        r"^SamsungClipboard.*",
        r"^SmartManager.*",
        r"^DeviceCare.*",
        r"^Knox.*",
        r"^Tima.*",
        r"^SELinux.*",
        r"^AUDIT.*",
        r"^WifiManager.*",
        r"^ConnectivityService.*",
        r"^NetworkMonitor.*",
        r"^Netd.*",
        r"^DnsResolver.*",
        r"^Telephony.*",
        r"^Ril.*",
        r"^IMS.*",
        r"^Vzw.*",
        r"^Carrier.*",
        r"^SamsungHealth.*",
        r"^SamsungPay.*",
        r"^SamsungPass.*",
        r"^Bixby.*",
        r"^VoiceWakeup.*",
        r"^SamsungCloud.*",
        r"^SamsungAccount.*",
        r"^SamsungBackup.*",
        r"^GameOptimizingService.*",
        r"^GameBooster.*",
        r"^GameTools.*",
        r"^EdgeLighting.*",
        r"^EdgePanel.*",
        r"^AlwaysOnDisplay.*",
        r"^Aod.*",
        r"^Fingerprint.*",
        r"^FaceRecognition.*",
        r"^Biometric.*",
        r"^SamsungDex.*",
        r"^MultiWindow.*",
        r"^SplitScreen.*",
        r"^PopUpView.*",
        r"^SamsungCamera.*",
        r"^Camera.*",
        r"^MediaProvider.*",
        r"^MediaScanner.*",
        r"^DownloadManager.*",
        r"^DownloadProvider.*",
        r"^Bluetooth.*",
        r"^Bt.*",
        r"^Gps.*",
        r"^Location.*",
        r"^FusedLocation.*",
        r"^Geofence.*",
        r"^ActivityManager.*",
        r"^WindowManager.*",
        r"^InputManager.*",
        r"^PowerManager.*",
        r"^AlarmManager.*",
        r"^JobScheduler.*",
        r"^PackageManager.*",
        r"^Installer.*",
        r"^DexOpt.*",
        r"^Vold.*",
        r"^MountService.*",
        r"^Usb.*",
        r"^AudioPolicy.*",
        r"^AudioFlinger.*",
        r"^AudioTrack.*",
        r"^AudioRecord.*",
        r"^MediaPlayer.*",
        r"^MediaCodec.*",
        r"^OMX.*",
        r"^SurfaceFlinger.*",
        r"^GraphicBuffer.*",
        r"^Hwc.*",
        r"^Gralloc.*",
        r"^ION.*",
        r"^V4L2.*",
        r"^CameraService.*",
        r"^CameraProvider.*",
        r"^CameraDevice.*",
        r"^CameraMetadata.*",
        r"^CameraCaptureSession.*",
        r"^CameraCapture.*",
        r"^CameraRequest.*",
        r"^CameraResult.*",
        r"^CameraBuffer.*",
        r"^CameraStream.*",
        r"^CameraThread.*",
        r"^CameraHAL.*",
        r"^Camera2.*",
        r"^Camera3.*",
        r"^CameraClient.*",
        r"^CameraServer.*",
        r"^CameraHAL3.*",
        r"^CameraMetadataNative.*",
        r"^CameraDeviceClient.*",
        r"^CameraServiceProxy.*",
        r"^CameraDeviceRemote.*",
        r"^CameraClientProxy.*",
    ])

    # Third-party app patterns that commonly spam ERROR/WARN
    third_party_tag_patterns: list[str] = field(default_factory=lambda: [
        r"^com\.facebook\..*",
        r"^com\.instagram\..*",
        r"^com\.whatsapp\..*",
        r"^com\.google\.android\.gms.*",
        r"^com\.google\.android\.apps\..*",
        r"^com\.android\.chrome.*",
        r"^org\.chromium\..*",
        r"^com\.spotify\..*",
        r"^com\.netflix\..*",
        r"^com\.twitter\..*",
        r"^com\.snapchat\..*",
        r"^com\.discord\..*",
        r"^com\.zoom\..*",
        r"^com\.microsoft\..*",
        r"^com\.adobe\..*",
        r"^com\.amazon\..*",
        r"^com\.uber\..*",
        r"^com\.lyft\..*",
        r"^com\.airbnb\..*",
        r"^com\.yelp\..*",
        r"^com\.tinder\..*",
        r"^com\.pinterest\..*",
        r"^com\.linkedin\..*",
        r"^com\.reddit\..*",
        r"^com\.tiktok\..*",
        r"^com\.zzoom\..*",
        r"^com\.viber\..*",
        r"^com\.telegram\..*",
        r"^com\.signal\..*",
        r"^com\.threema\..*",
        r"^com\.wire\..*",
        r"^org\.thunderdog\..*",
        r"^com\.protonmail\..*",
        r"^com\.tutanota\..*",
        r"^com\.fastmail\..*",
        r"^org\.k9mail\..*",
        r"^com\.fivem\..*",
        r"^com\.steam\..*",
        r"^com\.epicgames\..*",
        r"^com\.ea\..*",
        r"^com\.activision\..*",
        r"^com\.ubisoft\..*",
        r"^com\.rockstargames\..*",
        r"^com\.blizzard\..*",
        r"^com\.riotgames\..*",
        r"^com\.supercell\..*",
        r"^com\.king\..*",
        r"^com\.zynga\..*",
        r"^com\.gameloft\..*",
        r"^com\.rovio\..*",
        r"^com\.halfbrick\..*",
        r"^com\.miniclip\..*",
        r"^com\.niantic\..*",
        r"^com\.nintendo\..*",
        r"^com\.sony\..*",
        r"^com\.playstation\..*",
        r"^com\.xbox\..*",
        # Analytics and telemetry services
        r".*analytics.*",
        r".*telemetry.*",
        r".*metrics.*",
        r".*crashlytics.*",
        r".*firebase.*",
        r".*fabric.*",
        r".*amplitude.*",
        r".*mixpanel.*",
        r".*segment.*",
        r".*appcenter.*",
        r".*hockeyapp.*",
        r".*sentry.*",
        r".*bugsnag.*",
        r".*rollbar.*",
    ])

    # Message content patterns that indicate verbose/debug logging, not real errors
    verbose_message_patterns: list[str] = field(default_factory=lambda: [
        r".*verbose.*",
        r".*debug.*",
        r".*trace.*",
        r".*perf.*",
        r".*benchmark.*",
        r".*profiling.*",
        r".*timing.*",
        r".*duration.*",
        r".*elapsed.*",
        r".*performance.*",
        r".*statistics.*",
        r".*metric.*",
        r".*telemetry.*",
        r".*analytics.*",
        r".*reporting.*",
        r".*logging.*",
        r".*dump.*",
        r".*stack.*trace.*",
        r".*entering.*",
        r".*exiting.*",
        r".*started.*",
        r".*finished.*",
        r".*completed.*",
        r".*begin.*",
        r".*end.*",
        r".*init.*",
        r".*initialize.*",
        r".*construct.*",
        r".*destroy.*",
        r".*cleanup.*",
        r".*dispose.*",
        r".*release.*",
        r".*acquire.*",
        r".*obtain.*",
        r".*getInstance.*",
        r".*singleton.*",
        r".*factory.*",
        r".*builder.*",
        r".*callback.*",
        r".*listener.*",
        r".*observer.*",
        r".*handler.*",
        r".*runnable.*",
        r".*thread.*",
        r".*executor.*",
        r".*future.*",
        r".*promise.*",
        r".*async.*",
        r".*await.*",
        r".*synchroniz.*",
        r".*lock.*",
        r".*mutex.*",
        r".*semaphore.*",
        r".*condition.*",
        r".*wait.*",
        r".*notify.*",
        r".*signal.*",
        r".*broadcast.*",
        r".*intent.*",
        r".*pendingintent.*",
        r".*contentprovider.*",
        r".*contentresolver.*",
        r".*cursor.*",
        r".*query.*",
        r".*insert.*",
        r".*update.*",
        r".*delete.*",
        r".*transaction.*",
        r".*commit.*",
        r".*rollback.*",
        r".*sqlite.*",
        r".*room.*",
        r".*dao.*",
        r".*entity.*",
        r".*repository.*",
        r".*viewmodel.*",
        r".*livedata.*",
        r".*flow.*",
        r".*coroutine.*",
        r".*suspend.*",
        r".*launch.*",
        r".*scope.*",
        r".*job.*",
        r".*deferred.*",
        r".*channel.*",
        r".*select.*",
        r".*actor.*",
        r".*dispatcher.*",
        r".*default.*",
        r".*unconfined.*",
    ])

    # Known benign error/warning patterns (specific messages to ignore)
    benign_message_patterns: list[str] = field(default_factory=lambda: [
        r".*[EW]/.*: Failed to find provider.*",
        r".*[EW]/.*: Unable to resolve.*",
        r".*[EW]/.*: No implementation found.*",
        r".*[EW]/.*: Class not found.*",
        r".*[EW]/.*: Method not found.*",
        r".*[EW]/.*: Field not found.*",
        r".*[EW]/.*: Resource not found.*",
        r".*[EW]/.*: Connection refused.*",
        r".*[EW]/.*: Timeout.*",
        r".*[EW]/.*: Network unreachable.*",
        r".*[EW]/.*: Host unreachable.*",
        r".*[EW]/.*: DNS lookup failed.*",
        r".*[EW]/.*: Certificate.*",
        r".*[EW]/.*: SSL.*",
        r".*[EW]/.*: TLS.*",
        r".*[EW]/.*: Handshake.*",
        r".*[EW]/.*: Protocol.*",
        r".*[EW]/.*: Version mismatch.*",
        r".*[EW]/.*: Deprecated.*",
        r".*[EW]/.*: Obsolete.*",
        r".*[EW]/.*: Legacy.*",
        r".*[EW]/.*: Compatibility.*",
        r".*[EW]/.*: Fallback.*",
        r".*[EW]/.*: Retry.*",
        r".*[EW]/.*: Reconnect.*",
        r".*[EW]/.*: Reconnecting.*",
        r".*[EW]/.*: Backoff.*",
        r".*[EW]/.*: Throttl.*",
        r".*[EW]/.*: Rate limit.*",
        r".*[EW]/.*: Quota.*",
        r".*[EW]/.*: Limit.*",
        r".*[EW]/.*: Exceed.*",
        r".*[EW]/.*: Buffer.*",
        r".*[EW]/.*: Queue.*",
        r".*[EW]/.*: Pool.*",
        r".*[EW]/.*: Cache.*",
        r".*[EW]/.*: Memory.*",
        r".*[EW]/.*: Heap.*",
        r".*[EW]/.*: GC.*",
        r".*[EW]/.*: Allocation.*",
        r".*[EW]/.*: Fragment.*",
        r".*[EW]/.*: Leak.*",
        r".*[EW]/.*: Reference.*",
        r".*[EW]/.*: Weak.*",
        r".*[EW]/.*: Soft.*",
        r".*[EW]/.*: Phantom.*",
        r".*[EW]/.*: Finalize.*",
        r".*[EW]/.*: Cleanup.*",
        r".*[EW]/.*: Dispose.*",
        r".*[EW]/.*: Close.*",
        r".*[EW]/.*: Shutdown.*",
        r".*[EW]/.*: Terminate.*",
        r".*[EW]/.*: Exit.*",
        r".*[EW]/.*: Crash.*",
        r".*[EW]/.*: Exception.*",
        # Specific dex2oat and SELinux patterns
        r".*dex2oat.*",
        r".*SELinux.*",
    ])


# Default filter configuration
DEFAULT_FILTER_CONFIG = FilterConfig()


class LogcatModule:
    """Logcat management module."""

    def __init__(self, client: AdbClient) -> None:
        self.client = client
        self._filter_config = DEFAULT_FILTER_CONFIG

    def _extract_package(self, tag: str, message: str) -> str | None:
        """Extract package name from tag or message."""
        # Common patterns for package names in tags/messages
        import re
        # Pattern 1: com.package.name
        match = re.search(r'\b(com\.[a-zA-Z0-9_.]+)', tag)
        if match:
            return match.group(1)
        match = re.search(r'\b(com\.[a-zA-Z0-9_.]+)', message)
        if match:
            return match.group(1)
        # Pattern 2: android system components
        if tag.startswith("ActivityManager") or tag.startswith("PackageManager"):
            return "android.system"
        return None

    def _parse_logcat_output(self, output: str, format: str = "threadtime") -> list[LogEntry]:
        """Parse logcat output string into LogEntry objects."""
        entries = []
        for line in output.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            if format == "brief":
                # Brief format: D/Tag(pid): message
                import re
                match = re.match(r"^([VDIWEF])/(.+?)\((\d+)\):\s*(.*)$", line)
                if match:
                    level_char, tag, pid_str, message = match.groups()
                    level_map = {
                        'V': LogLevel.VERBOSE,
                        'D': LogLevel.DEBUG,
                        'I': LogLevel.INFO,
                        'W': LogLevel.WARN,
                        'E': LogLevel.ERROR,
                        'F': LogLevel.FATAL,
                    }
                    level = level_map.get(level_char, LogLevel.INFO)
                    pid = int(pid_str)
                    entries.append(LogEntry(
                        timestamp=datetime.now(),
                        pid=pid,
                        tid=pid,
                        level=level,
                        tag=tag,
                        message=message,
                        raw=line,
                        package=self._extract_package(tag, message)
                    ))
            else:
                # Threadtime format: MM-DD HH:MM:SS.mmm  pid  tid  L tag: message
                import re
                match = re.match(r"^(\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2}\.\d{3})\s+(\d+)\s+(\d+)\s+([VDIWEF])\s+(.+?):\s*(.*)$", line)
                if match:
                    date_str, time_str, pid_str, tid_str, level_char, tag, message = match.groups()
                    level_map = {
                        'V': LogLevel.VERBOSE,
                        'D': LogLevel.DEBUG,
                        'I': LogLevel.INFO,
                        'W': LogLevel.WARN,
                        'E': LogLevel.ERROR,
                        'F': LogLevel.FATAL,
                    }
                    level = level_map.get(level_char, LogLevel.INFO)
                    pid = int(pid_str)
                    tid = int(tid_str)
                    # Parse timestamp
                    try:
                        dt = datetime.strptime(f"{date_str} {time_str}", "%m-%d %H:%M:%S.%f")
                    except ValueError:
                        dt = datetime.now()
                    entries.append(LogEntry(
                        timestamp=dt,
                        pid=pid,
                        tid=tid,
                        level=level,
                        tag=tag,
                        message=message,
                        raw=line,
                        package=self._extract_package(tag, message)
                    ))
        return entries

    def stream(
        self,
        *filters: str,
        format: str = "threadtime",
        pid: int | None = None,
    ):
        """Stream logcat lines as a context manager for iteration."""
        return self.client.logcat_stream_iter(*filters, format=format, pid=pid)

    def set_filter_config(self, config: FilterConfig) -> None:
        """Set custom filter configuration."""
        self._filter_config = config

    def filter_false_positives(
        self,
        logs: list[LogEntry],
        filter_samsung: bool = True,
        filter_third_party: bool = True,
        filter_verbose: bool = True,
        filter_benign: bool = True,
    ) -> tuple[list[LogEntry], list[LogEntry]]:
        """
        Filter out false positive log entries that are verbose logging, not actual issues.

        Returns:
            Tuple of (filtered_logs, false_positives) where filtered_logs contains
            entries that are likely real issues, and false_positives contains the
            entries that were filtered out.
        """
        config = self._filter_config
        filtered = []
        false_positives = []

        for log in logs:
            is_false_positive = False

            # Check Samsung system tags
            if filter_samsung and config.samsung_tag_patterns:
                for pattern in config.samsung_tag_patterns:
                    if re.match(pattern, log.tag):
                        is_false_positive = True
                        break

            # Check third-party app tags
            if not is_false_positive and filter_third_party and config.third_party_tag_patterns:
                for pattern in config.third_party_tag_patterns:
                    if re.match(pattern, log.tag):
                        is_false_positive = True
                        break

            # Check verbose message patterns (only for WARN/ERROR/FATAL levels)
            if not is_false_positive and filter_verbose and config.verbose_message_patterns:
                if log.level in (LogLevel.WARN, LogLevel.ERROR, LogLevel.FATAL):
                    for pattern in config.verbose_message_patterns:
                        if re.match(pattern, log.message, re.IGNORECASE):
                            is_false_positive = True
                            break

            # Check benign message patterns
            if not is_false_positive and filter_benign and config.benign_message_patterns:
                for pattern in config.benign_message_patterns:
                    if re.match(pattern, log.raw, re.IGNORECASE):
                        is_false_positive = True
                        break

            if is_false_positive:
                false_positives.append(log)
            else:
                filtered.append(log)

        return filtered, false_positives

    def get_filtered_errors(
        self,
        lines: int = 100,
        filter_samsung: bool = True,
        filter_third_party: bool = True,
        filter_verbose: bool = True,
        filter_benign: bool = True,
    ) -> list[LogEntry]:
        """Get recent error logs with false positives filtered out."""
        logs = self.get_errors(lines=lines)
        filtered, _ = self.filter_false_positives(
            logs,
            filter_samsung=filter_samsung,
            filter_third_party=filter_third_party,
            filter_verbose=filter_verbose,
            filter_benign=filter_benign,
        )
        return filtered

    def get_filtered_warnings(
        self,
        lines: int = 100,
        filter_samsung: bool = True,
        filter_third_party: bool = True,
        filter_verbose: bool = True,
        filter_benign: bool = True,
    ) -> list[LogEntry]:
        """Get recent warning logs with false positives filtered out."""
        logs = self.get_warnings(lines=lines)
        filtered, _ = self.filter_false_positives(
            logs,
            filter_samsung=filter_samsung,
            filter_third_party=filter_third_party,
            filter_verbose=filter_verbose,
            filter_benign=filter_benign,
        )
        return filtered

    def get_filtered_crashes(
        self,
        lines: int = 50,
        filter_samsung: bool = True,
        filter_third_party: bool = True,
        filter_verbose: bool = True,
        filter_benign: bool = True,
    ) -> list[LogEntry]:
        """Get recent crashes with false positives filtered out."""
        logs = self.get_crashes(lines=lines)
        filtered, _ = self.filter_false_positives(
            logs,
            filter_samsung=filter_samsung,
            filter_third_party=filter_third_party,
            filter_verbose=filter_verbose,
            filter_benign=filter_benign,
        )
        return filtered

    def get_filtered_anrs(
        self,
        lines: int = 50,
        filter_samsung: bool = True,
        filter_third_party: bool = True,
        filter_verbose: bool = True,
        filter_benign: bool = True,
    ) -> list[LogEntry]:
        """Get recent ANRs with false positives filtered out."""
        logs = self.get_anrs(lines=lines)
        filtered, _ = self.filter_false_positives(
            logs,
            filter_samsung=filter_samsung,
            filter_third_party=filter_third_party,
            filter_verbose=filter_verbose,
            filter_benign=filter_benign,
        )
        return filtered

    def get_logs_with_stats(
        self,
        lines: int = 1000,
        filter_samsung: bool = True,
        filter_third_party: bool = True,
        filter_verbose: bool = True,
        filter_benign: bool = True,
    ) -> dict[str, Any]:
        """Get logs with filtering statistics."""
        logs = self.client.logcat(format="threadtime", lines=lines)
        filtered, false_positives = self.filter_false_positives(
            logs,
            filter_samsung=filter_samsung,
            filter_third_party=filter_third_party,
            filter_verbose=filter_verbose,
            filter_benign=filter_benign,
        )

        # Calculate stats
        stats = {
            "total": len(logs),
            "filtered": len(filtered),
            "false_positives": len(false_positives),
            "filter_rate": len(false_positives) / len(logs) if logs else 0.0,
            "by_level": {},
            "false_positive_by_tag": {},
        }

        for log in false_positives:
            level_name = log.level.name
            stats["by_level"][level_name] = stats["by_level"].get(level_name, 0) + 1
            stats["false_positive_by_tag"][log.tag] = stats["false_positive_by_tag"].get(log.tag, 0) + 1

        return {
            "filtered_logs": filtered,
            "false_positives": false_positives,
            "stats": stats,
        }

    def get_logs(
        self,
        *filters: str,
        format: str = "threadtime",
        lines: int = 100,
        pid: int | None = None,
    ) -> list[LogEntry]:
        """Get recent logcat entries."""
        return self.client.logcat(*filters, format=format, lines=lines, pid=pid)

    def get_errors(self, lines: int = 100) -> list[LogEntry]:
        """Get recent error logs."""
        return self.client.logcat("*:E", format="threadtime", lines=lines)

    def get_warnings(self, lines: int = 100) -> list[LogEntry]:
        """Get recent warning logs."""
        return self.client.logcat("*:W", format="threadtime", lines=lines)

    def get_crashes(self, lines: int = 50) -> list[LogEntry]:
        """Get recent crashes (AndroidRuntime:E)."""
        return self.client.logcat("AndroidRuntime:E", format="threadtime", lines=lines)

    def get_anrs(self, lines: int = 50) -> list[LogEntry]:
        """Get recent ANR traces."""
        return self.client.logcat("*:W", "*:E", format="threadtime", lines=lines)

    def find_crashes(self, since_minutes: int = 60) -> list[LogEntry]:
        """Find crashes in the last N minutes (alias for diagnostics compatibility)."""
        # Estimate lines based on minutes (roughly 100 lines per minute for active device)
        estimated_lines = min(since_minutes * 100, 5000)
        return self.find_crashes_in_buffer(lines=estimated_lines)

    def find_anrs(self, since_minutes: int = 60) -> list[LogEntry]:
        """Find ANRs in the last N minutes (alias for diagnostics compatibility)."""
        estimated_lines = min(since_minutes * 100, 5000)
        return self.find_anrs_in_buffer(lines=estimated_lines)

    def stream_logs(
        self,
        *filters: str,
        format: str = "threadtime",
        pid: int | None = None,
        callback: Callable[[LogEntry], None] | None = None,
    ) -> None:
        """Stream logcat in real-time."""
        self.client.logcat_stream(*filters, format=format, pid=pid, callback=callback)

    def find_crashes_in_buffer(self, lines: int = 500) -> list[LogEntry]:
        """Search for crashes in the full log buffer."""
        logs = self.client.logcat(format="threadtime", lines=lines)
        crashes = []
        for log in logs:
            if log.level in (LogLevel.ERROR, LogLevel.FATAL):
                if any(keyword in log.tag.lower() for keyword in ("runtime", "exception", "crash", "fatal")):
                    crashes.append(log)
        return crashes

    def find_anrs_in_buffer(self, lines: int = 500) -> list[LogEntry]:
        """Search for ANRs in the full log buffer."""
        logs = self.client.logcat(format="threadtime", lines=lines)
        anrs = []
        for log in logs:
            if log.level in (LogLevel.WARN, LogLevel.ERROR, LogLevel.FATAL):
                if "anr" in log.tag.lower() or "anr" in log.message.lower():
                    anrs.append(log)
        return anrs

    def find_permission_denials(self, lines: int = 500) -> list[LogEntry]:
        """Find permission denial logs."""
        logs = self.client.logcat(format="threadtime", lines=lines)
        denials = []
        for log in logs:
            if log.level == LogLevel.WARN or log.level == LogLevel.ERROR:
                if "permission" in log.message.lower() and "denied" in log.message.lower():
                    denials.append(log)
        return denials

    def find_native_crashes(self, lines: int = 500) -> list[LogEntry]:
        """Find native crashes (SIGSEGV, SIGABRT, etc.)."""
        logs = self.client.logcat(format="threadtime", lines=lines)
        crashes = []
        for log in logs:
            if log.level in (LogLevel.ERROR, LogLevel.FATAL):
                if any(sig in log.message.upper() for sig in ("SIGSEGV", "SIGABRT", "SIGFPE", "SIGILL", "SIGBUS")):
                    crashes.append(log)
        return crashes

    def get_app_logs(self, package_name: str, lines: int = 100) -> list[LogEntry]:
        """Get logs for a specific app by package name."""
        # First get PID
        try:
            pid_output = self.client.execute("shell", "pidof", package_name)
            pid = int(pid_output.strip()) if pid_output.strip() else None
        except Exception:
            pid = None

        if pid:
            return self.client.logcat(format="threadtime", lines=lines, pid=pid)
        return []

    def clear_logs(self) -> bool:
        """Clear logcat buffer."""
        self.client.logcat(clear=True)
        return True

    def save_logs_to_file(
        self,
        file_path: str,
        *filters: str,
        format: str = "threadtime",
        lines: int = 1000,
        base_dir: str | Path | None = None,
    ) -> int:
        """Save logs to file, returns number of entries saved.

        ``file_path`` is confined inside ``base_dir`` (default ``./logs``):
        ``..`` segments or symlinks resolving outside the base are rejected
        with :class:`PathEscapeError`. Pass ``base_dir`` explicitly to allow
        a different export location; the confinement still applies within it.
        """
        from .paths import confined_path

        base = Path(base_dir) if base_dir else Path("logs")
        # Bare names and relative paths land inside the base; absolute paths
        # and any ".." segments must still resolve inside it.
        target = confined_path(base, Path(base) / file_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        logs = self.client.logcat(*filters, format=format, lines=lines)
        with open(target, "w", encoding="utf-8") as f:
            for log in logs:
                f.write(log.raw + "\n")
        return len(logs)

    def get_log_stats(self, lines: int = 1000) -> dict:
        """Get statistics about log levels in recent logs."""
        logs = self.client.logcat(format="threadtime", lines=lines)
        stats: dict = {
            "total_lines": len(logs),
            "by_level": {},
            "by_tag": {},
        }
        for log in logs:
            level_name = log.level.name
            stats["by_level"][level_name] = stats["by_level"].get(level_name, 0) + 1
            stats["by_tag"][log.tag] = stats["by_tag"].get(log.tag, 0) + 1
        return stats

    def get_top_tags(self, lines: int = 1000, limit: int = 20) -> list[tuple[str, int]]:
        """Get most frequent log tags."""
        logs = self.client.logcat(format="threadtime", lines=lines)
        tag_counts: dict[str, int] = {}
        for log in logs:
            tag_counts[log.tag] = tag_counts.get(log.tag, 0) + 1
        return sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:limit]

    def monitor_for_crashes(
        self,
        callback: Callable[[LogEntry], None],
        package_name: str | None = None,
    ) -> None:
        """Monitor logcat for crashes and call callback when found."""
        def filter_crashes(entry: LogEntry) -> None:
            if entry.level in (LogLevel.ERROR, LogLevel.FATAL):
                if any(keyword in entry.tag.lower() for keyword in ("runtime", "exception", "crash", "fatal", "anr")):
                    if package_name is None or package_name in entry.tag or package_name in entry.message:
                        callback(entry)

        filters = ("*:E", "*:F") if not package_name else ("*:E", "*:F")
        self.client.logcat_stream(*filters, format="threadtime", callback=filter_crashes)

    def grep_logs(self, pattern: str, lines: int = 1000, case_sensitive: bool = False) -> list[LogEntry]:
        """Search logs for a regex pattern."""
        logs = self.client.logcat(format="threadtime", lines=lines)
        flags = 0 if case_sensitive else re.IGNORECASE
        compiled = re.compile(pattern, flags)
        matches = []
        for log in logs:
            if compiled.search(log.message) or compiled.search(log.tag):
                matches.append(log)
        return matches

