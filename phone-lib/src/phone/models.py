"""Typed data models for phone toolkit."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class BatteryHealth(str, Enum):
    """Battery health states from Android."""
    UNKNOWN = "Unknown"
    GOOD = "Good"
    OVERHEAT = "Overheat"
    DEAD = "Dead"
    OVER_VOLTAGE = "Over voltage"
    UNSPECIFIED_FAILURE = "Unspecified failure"
    COLD = "Cold"
    WATCHDOG_TIMER_EXPIRE = "Watchdog timer expire"
    SAFETY_TIMER_EXPIRE = "Safety timer expire"


class BatteryStatus(str, Enum):
    """Battery charging status."""
    UNKNOWN = "Unknown"
    CHARGING = "Charging"
    DISCHARGING = "Discharging"
    NOT_CHARGING = "Not charging"
    FULL = "Full"


class ThermalStatus(str, Enum):
    """Thermal throttling status."""
    NORMAL = "Normal"
    THROTTLED = "Throttled"
    SEVERE = "Severe"
    CRITICAL = "Critical"
    EMERGENCY = "Emergency"
    SHUTDOWN = "Shutdown"


class LogLevel(str, Enum):
    """Android log levels."""
    VERBOSE = "V"
    DEBUG = "D"
    INFO = "I"
    WARN = "W"
    ERROR = "E"
    FATAL = "F"
    SILENT = "S"


@dataclass(slots=True)
class BatteryInfo:
    """Battery information from dumpsys battery."""
    level: int  # 0-100
    health: BatteryHealth
    status: BatteryStatus
    temperature_c: float  # in Celsius (tenths of degree from Android)
    voltage_mv: int  # millivolts
    technology: str
    plugged_type: str  # AC, USB, Wireless, Unknown
    max_capacity_mah: int | None = None
    current_capacity_mah: int | None = None
    charge_cycles: int | None = None
    present: bool = True
    scale: int = 100

    @property
    def temperature_f(self) -> float:
        """Temperature in Fahrenheit."""
        return self.temperature_c * 9 / 5 + 32

    @property
    def is_charging(self) -> bool:
        return self.status == BatteryStatus.CHARGING

    @property
    def is_healthy(self) -> bool:
        return self.health == BatteryHealth.GOOD

    @property
    def temperature(self) -> float:
        """Temperature in Celsius (alias for diagnostics compatibility)."""
        return self.temperature_c

    @property
    def voltage(self) -> int:
        """Voltage in millivolts (alias for diagnostics compatibility)."""
        return self.voltage_mv

    @property
    def status_str(self) -> str:
        """Charging status as string (alias for diagnostics compatibility)."""
        return self.status.value

    @property
    def health_str(self) -> str:
        """Battery health as string (alias for diagnostics compatibility)."""
        return self.health.value

    @property
    def technology_str(self) -> str:
        """Battery technology (alias for diagnostics compatibility)."""
        return self.technology

    @property
    def capacity(self) -> int | None:
        """Current capacity in mAh (alias for diagnostics compatibility)."""
        return self.current_capacity_mah

    @property
    def cycle_count(self) -> int | None:
        """Charge cycles (alias for diagnostics compatibility)."""
        return self.charge_cycles


@dataclass(slots=True)
class StorageInfo:
    """Storage/partition information."""
    partition: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    filesystem: str
    mount_point: str

    @property
    def total_gb(self) -> float:
        return self.total_bytes / (1024 ** 3)

    @property
    def used_gb(self) -> float:
        return self.used_bytes / (1024 ** 3)

    @property
    def free_gb(self) -> float:
        return self.free_bytes / (1024 ** 3)

    @property
    def usage_percent(self) -> float:
        if self.total_bytes == 0:
            return 0.0
        return (self.used_bytes / self.total_bytes) * 100


@dataclass(slots=True)
class DeviceInfo:
    """Device identification and OS info."""
    serial: str
    model: str
    manufacturer: str
    brand: str
    device: str
    product: str
    android_version: str
    api_level: int
    security_patch: str  # YYYY-MM-DD format
    build_fingerprint: str
    build_id: str
    build_type: str
    build_tags: str
    build_number: str | None = None
    kernel_version: str | None = None
    bootloader: str | None = None
    hardware: str | None = None
    cpu_abi: str | None = None
    cpu_abi2: str | None = None
    screen_density: int | None = None
    screen_width: int | None = None
    screen_height: int | None = None
    total_memory: int | None = None


@dataclass(slots=True)
class LogEntry:
    """Single logcat entry."""
    timestamp: datetime
    pid: int
    tid: int
    level: LogLevel
    tag: str
    message: str
    raw: str
    package: str | None = None

    @classmethod
    def parse_brief(cls, line: str) -> LogEntry | None:
        """Parse brief format: D/Tag(1234): message"""
        import re
        # Format: V/D/I/W/E/F/Tag(pid): message
        match = re.match(r"^([VDIWEFS])/(.+?)\((\d+)\):\s*(.*)$", line.strip())
        if not match:
            return None
        level_char, tag, pid_str, message = match.groups()
        try:
            level = LogLevel(level_char)
        except ValueError:
            level = LogLevel.VERBOSE
        return cls(
            timestamp=datetime.now(),  # Brief format doesn't include timestamp
            pid=int(pid_str),
            tid=int(pid_str),
            level=level,
            tag=tag,
            message=message,
            raw=line,
        )

    @classmethod
    def parse_threadtime(cls, line: str) -> LogEntry | None:
        """Parse threadtime format: MM-DD HH:MM:SS.mmm PID TID LEVEL Tag: message"""
        import re
        # 11-01 01:37:50.214  1141  1149 E HeatmapThread: message
        match = re.match(
            r"^(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})\s+(\d+)\s+(\d+)\s+([VDIWEFS])\s+(.+?):\s*(.*)$",
            line.strip()
        )
        if not match:
            return None
        timestamp_str, pid_str, tid_str, level_char, tag, message = match.groups()
        try:
            timestamp = datetime.strptime(timestamp_str, "%m-%d %H:%M:%S.%f")
        except ValueError:
            timestamp = datetime.now()
        try:
            level = LogLevel(level_char)
        except ValueError:
            level = LogLevel.VERBOSE
        return cls(
            timestamp=timestamp,
            pid=int(pid_str),
            tid=int(tid_str),
            level=level,
            tag=tag,
            message=message,
            raw=line,
        )


@dataclass(slots=True)
class NetworkInfo:
    """Network connectivity information."""
    wifi_connected: bool
    wifi_ssid: str | None = None
    wifi_ip: str | None = None
    wifi_signal_dbm: int | None = None
    mobile_connected: bool = False
    mobile_type: str | None = None  # LTE, 5G, etc.
    mobile_ip: str | None = None
    dns_servers: list[str] = field(default_factory=list)
    gateway: str | None = None
    internet_reachable: bool = False


@dataclass(slots=True)
class ThermalZone:
    """Thermal zone temperature."""
    name: str
    temp_c: float  # millicelsius from sysfs
    type: str | None = None

    @property
    def temp_f(self) -> float:
        return self.temp_c * 9 / 5 + 32


@dataclass(slots=True)
class ThermalInfo:
    """Thermal throttling information."""
    zones: list[ThermalZone] = field(default_factory=list)
    cpu_throttled: bool = False
    gpu_throttled: bool = False
    status: ThermalStatus = ThermalStatus.NORMAL


@dataclass(slots=True)
class AppInfo:
    """Application package information."""
    package_name: str
    version_name: str | None = None
    version_code: int | None = None
    install_source: str | None = None
    install_time: datetime | None = None
    update_time: datetime | None = None
    flags: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    enabled: bool = True
    system_app: bool = False
    app_name: str | None = None

    @property
    def model(self) -> dict:
        """Return dictionary representation for JSON serialization."""
        return {
            "package_name": self.package_name,
            "version_name": self.version_name,
            "version_code": self.version_code,
            "install_source": self.install_source,
            "install_time": self.install_time.isoformat() if self.install_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
            "flags": self.flags,
            "permissions": self.permissions,
            "enabled": self.enabled,
            "system_app": self.system_app,
            "app_name": self.app_name,
        }


@dataclass(slots=True)
class CpuInfo:
    """CPU information."""
    cores: int
    architecture: str
    governors: list[str] = field(default_factory=list)
    frequencies_khz: list[int] = field(default_factory=list)
    current_freq_khz: list[int] = field(default_factory=list)
    load_percent: list[float] = field(default_factory=list)


@dataclass(slots=True)
class MemoryInfo:
    """Memory information."""
    total_kb: int
    free_kb: int
    available_kb: int
    cached_kb: int
    buffers_kb: int
    swap_total_kb: int = 0
    swap_free_kb: int = 0

    @property
    def total_mb(self) -> float:
        return self.total_kb / 1024

    @property
    def available_mb(self) -> float:
        return self.available_kb / 1024

    @property
    def usage_percent(self) -> float:
        if self.total_kb == 0:
            return 0.0
        return ((self.total_kb - self.available_kb) / self.total_kb) * 100


@dataclass(slots=True)
class HealthReport:
    """Complete device health report."""
    timestamp: datetime = field(default_factory=datetime.now)
    device: DeviceInfo | None = None
    battery: BatteryInfo | None = None
    storage: list[StorageInfo] = field(default_factory=list)
    network: NetworkInfo | None = None
    thermal: ThermalInfo | None = None
    cpu: CpuInfo | None = None
    memory: MemoryInfo | None = None
    recent_crashes: list[LogEntry] = field(default_factory=list)
    recent_anrs: list[LogEntry] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        from dataclasses import asdict
        return asdict(self)

    @property
    def is_healthy(self) -> bool:
        return len(self.issues) == 0

    @property
    def summary(self) -> str:
        parts = []
        if self.battery:
            parts.append(f"Battery: {self.battery.level}% ({self.battery.health.value})")
        if self.storage:
            main = next((s for s in self.storage if s.mount_point == "/data"), self.storage[0])
            parts.append(f"Storage: {main.usage_percent:.0f}% used")
        if self.network:
            parts.append(f"Network: {'Online' if self.network.internet_reachable else 'Offline'}")
        return " | ".join(parts)
