"""Galaxy Phone Toolkit - Python ADB wrapper library (Samsung Galaxy S/Note/A)."""

from __future__ import annotations

from .adb import AdbClient, create_client
from .apps import AppsModule
from .battery import BatteryModule
from .capabilities import DeviceProfile, describe_model, detect_profile
from .device import DeviceModule
from .exceptions import (
    AdbConnectionError,
    CommandFailedError,
    DeviceNotFoundError,
    DeviceUnauthorizedError,
    FileTransferError,
    ParseError,
    PhoneError,
    TimeoutError,
)
from .logcat import LogcatModule
from .models import (
    AppInfo,
    BatteryHealth,
    BatteryInfo,
    BatteryStatus,
    CpuInfo,
    DeviceInfo,
    HealthReport,
    LogEntry,
    LogLevel,
    MemoryInfo,
    NetworkInfo,
    RootInfo,
    StorageInfo,
    ThermalInfo,
    ThermalStatus,
    ThermalZone,
)
from .network import NetworkModule
from .root import RootModule
from .screen import ScreenModule
from .storage import StorageModule
from .termux import (
    TermuxApiCommand,
    TermuxBattery,
    TermuxBootManager,
    TermuxClient,
    TermuxCpuInfo,
    TermuxWifiInfo,
)
from .thermal import ThermalModule

__version__ = "0.1.0"
__author__ = "Phone Toolkit"

__all__ = [
    # Core
    "AdbClient",
    "create_client",
    # Exceptions
    "PhoneError",
    "DeviceNotFoundError",
    "DeviceUnauthorizedError",
    "CommandFailedError",
    "AdbConnectionError",
    "ParseError",
    "TimeoutError",
    "FileTransferError",
    # Models
    "DeviceInfo",
    "BatteryInfo",
    "BatteryHealth",
    "BatteryStatus",
    "StorageInfo",
    "LogEntry",
    "LogLevel",
    "NetworkInfo",
    "RootInfo",
    "ThermalInfo",
    "ThermalStatus",
    "ThermalZone",
    "AppInfo",
    "CpuInfo",
    "MemoryInfo",
    "HealthReport",
    # Modules
    "DeviceModule",
    "DeviceProfile",
    "detect_profile",
    "describe_model",
    "BatteryModule",
    "StorageModule",
    "LogcatModule",
    "NetworkModule",
    "RootModule",
    "ThermalModule",
    "AppsModule",
    "ScreenModule",
    # Termux
    "TermuxClient",
    "TermuxBattery",
    "TermuxWifiInfo",
    "TermuxCpuInfo",
    "TermuxApiCommand",
    "TermuxBootManager",
]
