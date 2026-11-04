"""Pytest configuration and fixtures for phone-lib tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from phone.models import LogEntry, LogLevel


@dataclass
class MockAdbResponse:
    """Mock ADB command response."""

    stdout: str = ""
    stderr: str = ""
    returncode: int = 0


# Create mock LogEntry objects for logcat testing
def create_mock_log_entries() -> list[LogEntry]:
    """Create a list of mock LogEntry objects for testing."""
    return [
        LogEntry(
            timestamp=datetime(2024, 11, 1, 14, 32, 45, 123000),
            pid=1234,
            tid=1234,
            level=LogLevel.DEBUG,
            tag="MainActivity",
            message="onCreate called",
            raw="11-01 14:32:45.123  1234  1234 D MainActivity: onCreate called",
        ),
        LogEntry(
            timestamp=datetime(2024, 11, 1, 14, 32, 45, 234000),
            pid=1234,
            tid=1235,
            level=LogLevel.INFO,
            tag="System.out",
            message="Debug message",
            raw="11-01 14:32:45.234  1234  1235 I System.out: Debug message",
        ),
        LogEntry(
            timestamp=datetime(2024, 11, 1, 14, 32, 45, 345000),
            pid=1234,
            tid=1236,
            level=LogLevel.WARN,
            tag="NetworkManager",
            message="Connection timeout",
            raw="11-01 14:32:45.345  1234  1236 W NetworkManager: Connection timeout",
        ),
        LogEntry(
            timestamp=datetime(2024, 11, 1, 14, 32, 45, 456000),
            pid=1234,
            tid=1237,
            level=LogLevel.ERROR,
            tag="DatabaseHelper",
            message="Failed to open database",
            raw="11-01 14:32:45.456  1234  1237 E DatabaseHelper: Failed to open database",
        ),
        LogEntry(
            timestamp=datetime(2024, 11, 1, 14, 32, 45, 567000),
            pid=5678,
            tid=5678,
            level=LogLevel.ERROR,
            tag="AndroidRuntime",
            message="FATAL EXCEPTION: main",
            raw="11-01 14:32:45.567  5678  5678 E AndroidRuntime: FATAL EXCEPTION: main",
        ),
        LogEntry(
            timestamp=datetime(2024, 11, 1, 14, 32, 45, 567000),
            pid=5678,
            tid=5678,
            level=LogLevel.ERROR,
            tag="AndroidRuntime",
            message="java.lang.NullPointerException",
            raw="11-01 14:32:45.567  5678  5678 E AndroidRuntime: java.lang.NullPointerException",
        ),
        LogEntry(
            timestamp=datetime(2024, 11, 1, 14, 32, 45, 567000),
            pid=5678,
            tid=5678,
            level=LogLevel.ERROR,
            tag="AndroidRuntime",
            message="    at com.example.app.MainActivity.onCreate(MainActivity.java:42)",
            raw="11-01 14:32:45.567  5678  5678 E AndroidRuntime:     at com.example.app.MainActivity.onCreate(MainActivity.java:42)",
        ),
        LogEntry(
            timestamp=datetime(2024, 11, 1, 14, 32, 45, 678000),
            pid=1234,
            tid=1238,
            level=LogLevel.INFO,
            tag="ActivityManager",
            message="Killing 5678:com.example.app/u0a123",
            raw="11-01 14:32:45.678  1234  1238 I ActivityManager: Killing 5678:com.example.app/u0a123",
        ),
        LogEntry(
            timestamp=datetime(2024, 11, 1, 14, 32, 46, 123000),
            pid=1234,
            tid=1239,
            level=LogLevel.WARN,
            tag="ActivityManager",
            message="ANR in com.example.app",
            raw="11-01 14:32:46.123  1234  1239 W ActivityManager: ANR in com.example.app",
        ),
        LogEntry(
            timestamp=datetime(2024, 11, 1, 14, 32, 46, 234000),
            pid=1234,
            tid=1240,
            level=LogLevel.ERROR,
            tag="PackageManager",
            message="Permission denied for package com.example.app",
            raw="11-01 14:32:46.234  1234  1240 E PackageManager: Permission denied for package com.example.app",
        ),
    ]


@pytest.fixture
def mock_adb_client() -> MagicMock:
    """Create a mock AdbClient with predefined responses."""
    client = MagicMock()
    client.serial = "RFCTA0AEKZP"

    # Default responses for common commands
    responses = {
        ("shell", "dumpsys", "battery"): MOCK_BATTERY_DUMPSYS,
        ("shell", "dumpsys", "batterystats", "--checkin"): MOCK_BATTERYSTATS_CHECKIN,
        ("shell", "df"): MOCK_DF_OUTPUT,
        ("shell", "cat", "/proc/mounts"): MOCK_PROC_MOUNTS,
        ("shell", "getprop"): MOCK_GETPROP_ALL,
        ("shell", "dumpsys", "package"): MOCK_DUMPSYS_PACKAGE,
        ("shell", "dumpsys", "wifi"): MOCK_DUMPSYS_WIFI,
        ("shell", "dumpsys", "connectivity"): MOCK_DUMPSYS_CONNECTIVITY,
        ("shell", "dumpsys", "thermalservice"): MOCK_DUMPSYS_THERMAL,
        ("shell", "cat", "/sys/class/thermal/thermal_zone0/temp"): "35000\n",
        ("shell", "cat", "/sys/class/thermal/thermal_zone1/temp"): "36000\n",
        ("shell", "cat", "/sys/class/thermal/thermal_zone2/temp"): "34000\n",
        ("shell", "cat", "/sys/class/thermal/thermal_zone3/temp"): "45000\n",
        ("shell", "cat", "/sys/class/thermal/thermal_zone4/temp"): "42000\n",
        ("shell", "cat", "/sys/class/thermal/thermal_zone0/type"): "cpu\n",
        ("shell", "cat", "/sys/class/thermal/thermal_zone1/type"): "cpu\n",
        ("shell", "cat", "/sys/class/thermal/thermal_zone2/type"): "gpu\n",
        ("shell", "cat", "/sys/class/thermal/thermal_zone3/type"): "battery\n",
        ("shell", "cat", "/sys/class/thermal/thermal_zone4/type"): "skin\n",
        (
            "shell",
            "ls",
            "/sys/class/thermal/",
        ): "thermal_zone0\nthermal_zone1\nthermal_zone2\nthermal_zone3\nthermal_zone4\n",
        ("shell", "ls", "/sys/devices/virtual/thermal/"): "",
        ("shell", "logcat", "-d", "-v", "threadtime"): MOCK_LOGCAT_THREADTIME,
        ("logcat", "-v", "threadtime", "-t", "10", "*:V"): MOCK_LOGCAT_THREADTIME,
        ("logcat", "-v", "threadtime", "-t", "50", "AndroidRuntime:E"): MOCK_LOGCAT_THREADTIME,
        ("logcat", "-v", "threadtime", "-t", "50", "ANR:E"): MOCK_LOGCAT_THREADTIME,
        ("logcat", "-v", "threadtime", "-t", "100", "*:E"): MOCK_LOGCAT_THREADTIME,
        ("logcat", "-v", "threadtime", "-t", "100", "*:W"): MOCK_LOGCAT_THREADTIME,
        ("logcat", "-v", "brief", "-t", "100", "*:V"): """D/Tag1(100): Message 1
E/Tag2(200): Error message
W/Tag3(300): Warning message
""",
        ("shell", "pm", "list", "packages"): MOCK_PM_LIST_PACKAGES,
        ("shell", "pm", "list", "packages", "-3"): MOCK_PM_LIST_PACKAGES_THIRD_PARTY,
        ("shell", "pm", "list", "packages", "-d"): MOCK_PM_LIST_PACKAGES_DISABLED,
        ("shell", "pm", "list", "packages", "-e"): MOCK_PM_LIST_PACKAGES_ENABLED,
        ("shell", "dumpsys", "activity", "services"): MOCK_DUMPSYS_ACTIVITY_SERVICES,
        ("shell", "cat", "/proc/version"): MOCK_PROC_VERSION,
        ("shell", "cat", "/proc/cpuinfo"): MOCK_PROC_CPUINFO,
        ("shell", "cat", "/proc/meminfo"): MOCK_PROC_MEMINFO,
        ("shell", "cmd", "activity", "top"): MOCK_CMD_ACTIVITY_TOP,
        ("shell", "pidof", "com.example.app"): MOCK_PIDOF,
        ("shell", "pm", "path", "com.example.app"): MOCK_PM_PATH,
        ("shell", "dumpsys", "package", "com.example.app"): MOCK_DUMPSYS_PACKAGE,
        ("shell", "dumpsys", "package", "com.bloatware.app"): MOCK_DUMPSYS_PACKAGE_BOLOATWARE,
        ("shell", "pm", "list", "packages", "com.example.app"): "package:com.example.app\n",
        ("shell", "pm", "list", "packages", "com.nonexistent.app"): "",
        ("shell", "which", "su"): "",
        ("shell", "ls", "/system/xbin/su"): "No such file or directory\n",
        ("shell", "ip", "addr", "show", "wlan0"): "inet 192.168.1.100/24\n",
        (
            "shell",
            "ping",
            "-c",
            "3",
            "-W",
            "5",
            "8.8.8.8",
        ): "PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.\n64 bytes from 8.8.8.8: icmp_seq=1 ttl=117 time=25.4 ms\n64 bytes from 8.8.8.8: icmp_seq=2 ttl=117 time=24.8 ms\n64 bytes from 8.8.8.8: icmp_seq=3 ttl=117 time=26.1 ms\n--- 8.8.8.8 ping statistics---\n3 packets transmitted, 3 received, 0% packet loss, time 2003ms\n",
        (
            "shell",
            "cat",
            "/proc/net/route",
        ): "Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\tMTU\tWindow\tIRTT\nwlan0\t00000000\t0101A8C0\t0003\t0\t0\t0\t00000000\t0\t0\t0\n",
        (
            "shell",
            "cat",
            "/proc/net/dev",
        ): "Inter-|   Receive                                                |  Transmit\n face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed\n  wlan0: 1000000   5000    0    0    0     0          0         0  2000000   6000    0    0    0     0       0          0\n",
        ("shell", "getprop", "ro.build.version.security_patch"): "2024-01-01\n",
        ("shell", "getprop", "ro.build.version.release"): "14\n",
        ("shell", "getprop", "ro.build.version.sdk"): "34\n",
        (
            "shell",
            "getprop",
            "ro.build.fingerprint",
        ): "samsung/o2sxxx/o2s:14/UP1A.231005.007/S906BXXU2BWK1:user/release-keys\n",
        ("shell", "getprop", "ro.product.model"): "SM-S906B\n",
        ("shell", "dumpsys", "telephony.registry"): "mDataConnectionState=2\n",
        ("shell", "getprop", "net.dns1"): "192.168.1.1\n",
        ("shell", "getprop", "net.dns2"): "8.8.8.8\n",
        ("shell", "getprop", "net.dns3"): "\n",
        ("shell", "getprop", "net.dns4"): "\n",
        ("shell", "ip", "route", "show", "default"): "default via 192.168.1.1 dev wlan0\n",
        ("shell", "cat", "/sys/class/net/wlan0/statistics/rx_bytes"): "1000000\n",
        ("shell", "cat", "/sys/class/net/wlan0/statistics/tx_bytes"): "2000000\n",
        ("shell", "timeout", "3", "nc", "-z", "-w", "3", "8.8.8.8", "53"): "succeeded!\n",
        ("shell", "nslookup", "google.com"): "Name: google.com\nAddress: 142.250.190.46\n",
        (
            "shell",
            "curl",
            "-s",
            "-o",
            "/dev/null",
            "-w",
            "%{http_code}",
            "--max-time",
            "5",
            "http://www.google.com",
        ): "200\n",
        ("shell", "echo test"): "test\n",
        ("shell", "echo", "test"): "test\n",
        ("shell", "getprop", "gsm.network.type"): "LTE\n",
        ("shell", "ip", "addr", "show", "rmnet0"): "inet 10.0.0.1/24\n",
        ("shell", "ip", "addr", "show", "rmnet1"): "",
        ("shell", "ip", "addr", "show", "rmnet_data0"): "",
        ("shell", "ip", "addr", "show", "ccmni0"): "",
        (
            "shell",
            "dumpsys",
            "wifi",
            "|",
            "grep",
            "-A",
            "20",
            "ScanResult",
        ): """ScanResult[0]: BSSID: aa:bb:cc:dd:ee:ff SSID: "MyWiFiNetwork" freq: 2437 level: -45 timestamp: 123456789 distanceCm: -1 distanceSdCm: -1 venAnpi: 0 venMcs: 0 venNss: 0 venRxStreams: 0 venTxStreams: 0
ScanResult[1]: BSSID: 11:22:33:44:55:66 SSID: "OtherNetwork" freq: 5180 level: -65 timestamp: 123456790 distanceCm: -1 distanceSdCm: -1 venAnpi: 0 venMcs: 0 venNss: 0 venRxStreams: 0 venTxStreams: 0
""",
    }

    def mock_execute(*args, **kwargs):
        # Allow tests to override by setting return_value on the mock
        rv = client.execute.return_value
        if isinstance(rv, str) and rv != "":
            return rv
        key = tuple(args)
        if key in responses:
            return responses[key]
        # Handle dynamic logcat calls
        if args and args[0] == "logcat":
            # Check for various logcat call patterns
            if "-t" in args:
                return MOCK_LOGCAT_THREADTIME
            return MOCK_LOGCAT_THREADTIME
        # Handle getprop calls
        if args and args[0] == "getprop" and len(args) == 2:
            prop_key = args[1]
            for line in MOCK_GETPROP_ALL.strip().split("\n"):
                if prop_key in line:
                    match = line.strip()
                    if "]: [" in match:
                        return match.split("]: [")[1].rstrip("]") + "\n"
            return ""
        # Handle cat /sys/class/thermal/*/type
        if len(args) >= 3 and args[0] == "shell" and args[1] == "cat" and "/type" in args[2]:
            if "thermal_zone0" in args[2]:
                return "cpu\n"
            elif "thermal_zone1" in args[2]:
                return "cpu\n"
            elif "thermal_zone2" in args[2]:
                return "gpu\n"
            elif "thermal_zone3" in args[2]:
                return "battery\n"
            elif "thermal_zone4" in args[2]:
                return "skin\n"
            return "unknown\n"
        # Default empty response
        return ""

    client.execute = MagicMock(side_effect=mock_execute)
    client.execute_async = AsyncMock(side_effect=mock_execute)
    client.get_devices = MagicMock(return_value=[{"serial": "RFCTA0AEKZP", "state": "device"}])
    client.is_connected = MagicMock(return_value=True)
    client.get_serial = MagicMock(return_value="RFCTA0AEKZP")

    # Mock shell method - delegates to execute
    def mock_shell(command: str, *, timeout: float | None = None) -> str:
        return client.execute("shell", command, timeout=timeout)

    client.shell = MagicMock(side_effect=mock_shell)

    # Mock logcat method with proper filtering support
    def mock_logcat(
        *filters,
        format: str = "threadtime",
        lines: int = 100,
        pid: int | None = None,
        clear: bool = False,
        tag: str | None = None,
        **kwargs,
    ):
        """Mock logcat that supports filtering."""
        if clear:
            return []  # Actual implementation returns empty list

        # Check if tests have set a custom string return value on execute (for backward compat)
        # Parse it into LogEntry objects
        rv = client.execute.return_value
        if isinstance(rv, str) and rv != "":
            # Parse the string logcat output
            from phone.logcat import LogcatModule

            module = LogcatModule(client)
            all_entries = module._parse_logcat_output(rv, format=format)
        elif hasattr(client, "_logcat_return_value") and isinstance(
            getattr(client, "_logcat_return_value", None), list
        ):
            all_entries = client._logcat_return_value
        else:
            all_entries = create_mock_log_entries()

        # Apply tag filter
        if tag:
            all_entries = [e for e in all_entries if e.tag == tag]

        # Apply level filters (e.g., "*:E", "*:W") - handle both positional filters and filters kwarg
        # The filters kwarg is passed as a tuple/list like ("*:E",)
        filter_list = list(filters)
        if "filters" in kwargs:
            filter_val = kwargs["filters"]
            if isinstance(filter_val, (list, tuple)):
                filter_list.extend(filter_val)
            else:
                filter_list.append(filter_val)

        # Apply filters with OR logic (entry passes if it matches ANY filter)
        # This matches real logcat behavior
        if filter_list:

            def matches_any_filter(entry: LogEntry) -> bool:
                for f in filter_list:
                    if f.endswith(":E") and entry.level == LogLevel.ERROR:
                        return True
                    elif f.endswith(":W") and entry.level == LogLevel.WARN:
                        return True
                    elif f.endswith(":I") and entry.level == LogLevel.INFO:
                        return True
                    elif f.endswith(":D") and entry.level == LogLevel.DEBUG:
                        return True
                    elif f.endswith(":V") and entry.level == LogLevel.VERBOSE:
                        return True
                    elif f.endswith(":F") and entry.level == LogLevel.FATAL:
                        return True
                return False

            all_entries = [e for e in all_entries if matches_any_filter(e)]

        # Apply PID filter
        if pid is not None:
            all_entries = [e for e in all_entries if e.pid == pid]

        # Limit lines
        return all_entries[:lines]

    # For brief format, we need different mock entries
    def mock_logcat_brief(
        *filters,
        format: str = "threadtime",
        lines: int = 100,
        pid: int | None = None,
        clear: bool = False,
        tag: str | None = None,
        **kwargs,
    ):
        """Mock logcat for brief format."""
        if clear:
            return []
        # Return brief format entries
        return [
            LogEntry(
                timestamp=datetime(2024, 11, 1, 14, 32, 45, 123000),
                pid=100,
                tid=100,
                level=LogLevel.DEBUG,
                tag="Tag1",
                message="Message 1",
                raw="D/Tag1(100): Message 1",
            ),
            LogEntry(
                timestamp=datetime(2024, 11, 1, 14, 32, 45, 234000),
                pid=200,
                tid=200,
                level=LogLevel.ERROR,
                tag="Tag2",
                message="Error message",
                raw="E/Tag2(200): Error message",
            ),
            LogEntry(
                timestamp=datetime(2024, 11, 1, 14, 32, 45, 345000),
                pid=300,
                tid=300,
                level=LogLevel.WARN,
                tag="Tag3",
                message="Warning message",
                raw="W/Tag3(300): Warning message",
            ),
        ][:lines]

    # Make logcat mock handle format parameter
    def mock_logcat_wrapper(*args, **kwargs):
        format_val = kwargs.get("format", "threadtime")
        if format_val == "brief":
            return mock_logcat_brief(*args, **kwargs)
        return mock_logcat(*args, **kwargs)

    client.logcat = MagicMock(side_effect=mock_logcat_wrapper)
    client.logcat_stream = MagicMock(return_value=None)

    return client


@pytest.fixture
def mock_adb_client_error() -> MagicMock:
    """Create a mock AdbClient that raises errors."""
    from phone.exceptions import DeviceNotFoundError, PhoneError

    client = MagicMock()
    client.serial = "RFCTA0AEKZP"
    client.execute = MagicMock(side_effect=PhoneError("Command failed"))
    client.execute_async = AsyncMock(side_effect=PhoneError("Command failed"))
    client.get_devices = MagicMock(side_effect=DeviceNotFoundError("No devices found"))
    client.is_connected = MagicMock(return_value=False)

    return client


# Mock data fixtures
MOCK_BATTERY_DUMPSYS = """Current Battery Service state:
  AC powered: false
  USB powered: true
  Wireless powered: false
  Max charging current: 0
  Max charging voltage: 0
  Charge counter: 3200
  status: 2
  health: 2
  present: true
  level: 78
  scale: 100
  voltage: 4123
  temperature: 295
  technology: Li-ion
"""

MOCK_BATTERY_DUMPSYS_DIFFERENT = """Current Battery Service state:
  AC powered: false
  USB powered: false
  Wireless powered: false
  Max charging current: 0
  Max charging voltage: 0
  Charge counter: 3200
  status: 3
  health: 3
  present: true
  level: 50
  scale: 100
  voltage: 4000
  temperature: 320
  technology: Li-ion
"""

MOCK_BATTERY_NOT_PRESENT = """Current Battery Service state:
  AC powered: false
  USB powered: false
  Wireless powered: false
  Max charging current: 0
  Max charging voltage: 0
  Charge counter: 0
  status: 1
  health: 1
  present: false
  level: 0
  scale: 100
  voltage: 0
  temperature: 0
  technology: Li-ion
"""

MOCK_BATTERYSTATS_CHECKIN = """9,0,100,500000,100,42,300,0,0,0,0,0,0,0,0,0,0,0,0,0
"""

MOCK_DF_OUTPUT = """Filesystem     1K-blocks      Used Available Use% Mounted on
/dev/root        2097152    1200000    897152  58% /
/dev/block/dm-0   5242880    3500000   1742880  67% /data
/dev/block/dm-1   1048576     800000    248576  77% /cache
/dev/block/dm-2   52428800   40000000  12428800  77% /sdcard
"""

MOCK_PROC_MOUNTS = """rootfs / rootfs ro,relatime 0 0
tmpfs /dev tmpfs rw,seclabel,nosuid,relatime,mode=755 0 0
devpts /dev/pts devpts rw,seclabel,relatime,mode=600 0 0
proc /proc proc rw,relatime 0 0
sysfs /sys sysfs rw,seclabel,relatime 0 0
selinuxfs /sys/fs/selinux selinuxfs rw,seclabel,relatime 0 0
/dev/block/dm-0 /data f2fs rw,seclabel,relatime 0 0
/dev/block/dm-2 /sdcard vfat rw,relatime 0 0
"""

MOCK_GETPROP_ALL = """[ro.product.model]: [SM-S906B]
[ro.product.manufacturer]: [samsung]
[ro.product.brand]: [samsung]
[ro.product.device]: [o2s]
[ro.product.name]: [o2sxxx]
[ro.build.version.release]: [14]
[ro.build.version.sdk]: [34]
[ro.build.version.security_patch]: [2024-01-01]
[ro.build.fingerprint]: [samsung/o2sxxx/o2s:14/UP1A.231005.007/S906BXXU2BWK1:user/release-keys]
[ro.build.id]: [UP1A.231005.007]
[ro.build.type]: [user]
[ro.build.tags]: [release-keys]
[ro.kernel.version]: [5.15.100-12345678]
[ro.bootloader]: [S906BXXU2BWK1]
[ro.hardware]: [qcom]
[ro.product.cpu.abi]: [arm64-v8a]
[ro.product.cpu.abi2]: []
[ro.sf.lcd_density]: [420]
[ro.hwui.text_large_cache_width]: [2048]
[ro.hwui.text_large_cache_height]: [1024]
"""

MOCK_PROC_VERSION = """Linux version 5.15.100-12345678 (android-build@system) (gcc (GCC) 11.2.0, GNU ld (GNU Binutils) 2.38) #1 SMP PREEMPT Mon Jan 1 12:00:00 UTC 2024
"""

MOCK_PROC_CPUINFO = """Processor	: AArch64 Processor rev 1 (aarch64)
processor	: 0
BogoMIPS	: 38.40
Features	: fp asimd evtstrm aes pmull sha1 sha2 crc32 cpuid
CPU implementer	: 0x41
CPU architecture: 8
CPU variant	: 0x0
CPU part	: 0xd46
CPU revision	: 1

processor	: 1
BogoMIPS	: 38.40
Features	: fp asimd evtstrm aes pmull sha1 sha2 crc32 cpuid
CPU implementer	: 0x41
CPU architecture: 8
CPU variant	: 0x0
CPU part	: 0xd46
CPU revision	: 1

processor	: 2
BogoMIPS	: 38.40
Features	: fp asimd evtstrm aes pmull sha1 sha2 crc32 cpuid
CPU implementer	: 0x41
CPU architecture: 8
CPU variant	: 0x0
CPU part	: 0xd46
CPU revision	: 1

processor	: 3
BogoMIPS	: 38.40
Features	: fp asimd evtstrm aes pmull sha1 sha2 crc32 cpuid
CPU implementer	: 0x41
CPU architecture: 8
CPU variant	: 0x0
CPU part	: 0xd46
CPU revision	: 1

Hardware	: Qualcomm Technologies, Inc SM8450
Revision	: 0000
Serial		: 0000000000000000
"""

MOCK_PROC_MEMINFO = """MemTotal:        8192000 kB
MemFree:          1024000 kB
MemAvailable:     2048000 kB
Buffers:           512000 kB
Cached:           2048000 kB
SwapCached:            0 kB
Active:           3072000 kB
Inactive:         1536000 kB
Active(anon):     2048000 kB
Inactive(anon):   1024000 kB
Active(file):     1024000 kB
Inactive(file):    512000 kB
Unevictable:           0 kB
Mlocked:               0 kB
SwapTotal:             0 kB
SwapFree:              0 kB
Dirty:                 0 kB
Writeback:             0 kB
AnonPages:        2048000 kB
Mapped:            512000 kB
Shmem:             512000 kB
Slab:              256000 kB
SReclaimable:      128000 kB
SUnreclaim:        128000 kB
KernelStack:        64000 kB
PageTables:        128000 kB
NFS_Unstable:          0 kB
Bounce:                0 kB
WritebackTmp:          0 kB
CommitLimit:     4096000 kB
Committed_AS:    4096000 kB
VmallocTotal:   34359738367 kB
VmallocUsed:           0 kB
VmallocChunk:          0 kB
Percpu:             16384 kB
HardwareCorrupted:     0 kB
AnonHugePages:    1024000 kB
ShmemHugePages:        0 kB
ShmemPmdMapped:        0 kB
FileHugePages:         0 kB
FilePmdMapped:         0 kB
HugePages_Total:       0
HugePages_Free:        0
HugePages_Rsvd:        0
HugePages_Surp:        0
HugePages_size:       2048 kB
DirectMap4k:       1024000 kB
DirectMap2M:       2048000 kB
DirectMap1G:           0 kB
"""

MOCK_DUMPSYS_PACKAGE = """Package [com.example.app] (12345):
  userId=10123
  pkg=Package{abc123 com.example.app}
  codePath=/data/app/~~abc123==/com.example.app-efg456==/base.apk
  resourcePath=/data/app/~~abc123==/com.example.app-efg456==/base.apk
  legacyNativeLibraryDir=/data/app/~~abc123==/com.example.app-efg456==/lib/arm64
  primaryCpuAbi=arm64-v8a
  secondaryCpuAbi=null
  versionCode=45 minSdk=24 targetSdk=34
  versionName=1.2.3
  splits=[base]
  applicationInfo=ApplicationInfo{abc123 com.example.app}
  flags=[ HAS_CODE ALLOW_CLEAR_USER_DATA ALLOW_BACKUP ]
  dataDir=/data/user/0/com.example.app
  supportsScreens=[small, medium, large, xlarge, resizeable, anyDensity]
  timeStamp=2024-01-15 14:32:00
  firstInstallTime=1705333920000
  lastUpdateTime=1710063300000
  installerPackageName=com.android.vending
  permissions:
    android.permission.INTERNET: granted=true
    android.permission.CAMERA: granted=true
    android.permission.ACCESS_FINE_LOCATION: granted=false
  grantedPermissions:
    android.permission.INTERNET
    android.permission.CAMERA
"""

MOCK_DUMPSYS_PACKAGE_BOLOATWARE = """Package [com.bloatware.app] (54321):
  userId=10124
  pkg=Package{abc123 com.bloatware.app}
  codePath=/data/app/~~abc123==/com.bloatware.app-efg456==/base.apk
  resourcePath=/data/app/~~abc123==/com.bloatware.app-efg456==/base.apk
  legacyNativeLibraryDir=/data/app/~~abc123==/com.bloatware.app-efg456==/lib/arm64
  primaryCpuAbi=arm64-v8a
  secondaryCpuAbi=null
  versionCode=10 minSdk=24 targetSdk=34
  versionName=2.0.0
  splits=[base]
  applicationInfo=ApplicationInfo{abc123 com.bloatware.app}
  flags=[ DISABLED HAS_CODE ]
  dataDir=/data/user/0/com.bloatware.app
  supportsScreens=[small, medium, large, xlarge, resizeable, anyDensity]
  timeStamp=2024-01-15 14:32:00
  firstInstallTime=1705333920000
  lastUpdateTime=1710063300000
  installerPackageName=com.android.vending
  permissions:
    android.permission.INTERNET: granted=true
"""

MOCK_DUMPSYS_WIFI = """Wi-Fi is enabled
Supplicant state: COMPLETED
mNetworkInfo: type: WIFI[], state: CONNECTED/CONNECTED, reason: (unspecified), extra: "MyWiFiNetwork", roaming: false
BSSID: aa:bb:cc:dd:ee:ff
SSID: "MyWiFiNetwork"
IP address: 192.168.1.100
Signal strength: -45 dBm
RSSI: -45
Link speed: 72 Mbps
Frequency: 2437 MHz
"""

MOCK_DUMPSYS_CONNECTIVITY = """NetworkInfo: type: WIFI[], state: CONNECTED/CONNECTED, reason: (unspecified), extra: "MyWiFiNetwork", roaming: false, failover: false, isAvailable: true
NetworkInfo: type: MOBILE[], state: DISCONNECTED/DISCONNECTED, reason: (unspecified), extra: "mycarrier", roaming: false, failover: false, isAvailable: false
DNS servers: 192.168.1.1, 8.8.8.8
Gateway: 192.168.1.1
"""

MOCK_DUMPSYS_THERMAL = """Thermal Service:
Thermal zones:
  cpu0-thermal: temp=35000 type=cpu
  cpu1-thermal: temp=36000 type=cpu
  gpu-thermal: temp=34000 type=gpu
  battery-thermal: temp=45000 type=battery
  skin-thermal: temp=42000 type=skin
Throttling: none
"""

MOCK_DUMPSYS_THERMAL_CRITICAL = """Thermal Service:
Thermal zones:
  cpu0-thermal: temp=35000 type=cpu
  cpu1-thermal: temp=36000 type=cpu
  gpu-thermal: temp=34000 type=gpu
  battery-thermal: temp=55000 type=battery
  skin-thermal: temp=42000 type=skin
Throttling: throttled
"""

MOCK_LOGCAT_THREADTIME = """11-01 14:32:45.123  1234  1234 D MainActivity: onCreate called
11-01 14:32:45.234  1234  1235 I System.out: Debug message
11-01 14:32:45.345  1234  1236 W NetworkManager: Connection timeout
11-01 14:32:45.456  1234  1237 E DatabaseHelper: Failed to open database
11-01 14:32:45.567  5678  5678 E AndroidRuntime: FATAL EXCEPTION: main
11-01 14:32:45.567  5678  5678 E AndroidRuntime: java.lang.NullPointerException
11-01 14:32:45.567  5678  5678 E AndroidRuntime:     at com.example.app.MainActivity.onCreate(MainActivity.java:42)
11-01 14:32:45.678  1234  1238 I ActivityManager: Killing 5678:com.example.app/u0a123
11-01 14:32:46.123  1234  1239 W ActivityManager: ANR in com.example.app
11-01 14:32:46.234  1234  1240 E PackageManager: Permission denied for package com.example.app
"""

MOCK_PM_LIST_PACKAGES = """package:com.android.systemui
package:com.android.settings
package:com.example.app
package:com.another.app
package:com.samsung.android.app.spage
"""

MOCK_PM_LIST_PACKAGES_THIRD_PARTY = """package:com.example.app
package:com.another.app
"""

MOCK_PM_LIST_PACKAGES_DISABLED = """package:com.bloatware.app
"""

MOCK_PM_LIST_PACKAGES_ENABLED = """package:com.android.systemui
package:com.android.settings
package:com.example.app
package:com.another.app
"""

MOCK_DUMPSYS_ACTIVITY_SERVICES = """Running services:
  com.example.app/.MyService
  com.another.app/.AnotherService
"""

MOCK_CMD_ACTIVITY_TOP = """ACTIVITY MANAGER RUNNING ACTIVITIES
  Running activities (most recent first):
    TaskRecord{1234 com.example.app}
    TaskRecord{5678 com.another.app}
"""

MOCK_PIDOF = """1234
"""

MOCK_PM_PATH = """package:/data/app/~~abc123==/com.example.app-efg456==/base.apk
"""


# Additional mock data for specific tests
@pytest.fixture
def mock_battery_info():
    """Expected parsed battery info from mock data."""
    return {
        "level": 78,
        "health": "Good",
        "status": "Charging",
        "temperature_c": 29.5,
        "voltage_mv": 4123,
        "technology": "Li-ion",
        "plugged_type": "USB",
        "present": True,
        "scale": 100,
    }


@pytest.fixture
def mock_storage_info():
    """Expected parsed storage info from mock data."""
    return [
        {
            "mount_point": "/",
            "total_gb": 2.0,
            "used_gb": 1.14,
            "free_gb": 0.86,
            "usage_percent": 58.0,
        },
        {
            "mount_point": "/data",
            "total_gb": 5.0,
            "used_gb": 3.34,
            "free_gb": 1.66,
            "usage_percent": 67.0,
        },
    ]


@pytest.fixture
def mock_log_entries():
    """Mock logcat entries for testing."""
    return create_mock_log_entries()
