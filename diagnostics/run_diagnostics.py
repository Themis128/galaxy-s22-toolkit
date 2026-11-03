#!/usr/bin/env python3
# ruff: noqa: T201  # CLI output requires print statements
"""
Galaxy S22+ Diagnostics Automation Module

Scheduled health check runner that uses the phone-lib to perform comprehensive
device diagnostics and generate reports with configurable notifications.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

# Add phone-lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "phone-lib" / "src"))

from phone import (
    create_client,
    DeviceModule,
    BatteryModule,
    StorageModule,
    LogcatModule,
    NetworkModule,
    ThermalModule,
    AppsModule,
)
from phone.models import (
    HealthReport,
    BatteryHealth,
    LogLevel,
)


@dataclass
class CheckResult:
    """Result of a single health check."""
    name: str
    status: str  # "pass", "warning", "fail", "error"
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0.0


@dataclass
class DiagnosticConfig:
    """Configuration loaded from config.yaml."""
    device: dict
    thresholds: dict
    notifications: dict
    schedule: dict
    output: dict
    advanced: dict
    # Optional sections consumed by other components (CLI/dashboard repair)
    repair: dict = field(default_factory=dict)


class DiagnosticsRunner:
    """Main diagnostics runner."""
    
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config = self._load_config()
        self.client = None
        self.results: list[CheckResult] = []
        self.start_time = datetime.now()
        self.output_root = Path(__file__).resolve().parent
        self._setup_logging()
    
    def _load_config(self) -> DiagnosticConfig:
        """Load configuration from YAML file."""
        with open(self.config_path, 'r') as f:
            data = yaml.safe_load(f)
        return DiagnosticConfig(**data)
    
    def _setup_logging(self) -> None:
        """Set up logging configuration."""
        log_config = self.config.notifications.get('log_file', {})
        if log_config.get('enabled', True):
            # Anchored to the package dir like the reports, so the log lands
            # in the same place regardless of the caller's working directory
            log_path = self.output_root / log_config.get('path', 'logs/diagnostics.log')
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            handlers = [logging.FileHandler(log_path)]
            if sys.stdout is not None:  # None under pythonw (scheduled run)
                handlers.append(logging.StreamHandler(sys.stdout))
            logging.basicConfig(
                level=logging.DEBUG if self.config.advanced.get('verbose', False) else logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s',
                handlers=handlers,
            )
        else:
            logging.basicConfig(
                level=logging.DEBUG if self.config.advanced.get('verbose', False) else logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s',
                handlers=[logging.StreamHandler(sys.stdout)]
            )
        self.logger = logging.getLogger(__name__)
    
    def _create_client(self) -> None:
        """Create ADB client with wireless auto-reconnect from config."""
        device_cfg = self.config.device
        adb_path = device_cfg.get('adb_path') or None
        wireless = device_cfg.get('wireless_adb') or None
        if wireless:
            wireless = {**wireless, "preferred_serial": device_cfg.get('serial')}
        self.client = create_client(wireless=wireless, adb_path=adb_path)
        self.logger.info(f"Connected to device: {self.client.serial or 'auto-detect'}")
    
    def _run_check(self, name: str, check_func, *args, **kwargs) -> CheckResult:
        """Run a single check with timing and error handling."""
        start = time.perf_counter()
        try:
            result = check_func(*args, **kwargs)
            duration = (time.perf_counter() - start) * 1000
            if isinstance(result, CheckResult):
                result.duration_ms = duration
                return result
            return CheckResult(
                name=name,
                status="pass",
                message=str(result) if result else "Check passed",
                duration_ms=duration
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            self.logger.error(f"Check '{name}' failed: {e}")
            return CheckResult(
                name=name,
                status="error",
                message=f"Check failed: {e}",
                duration_ms=duration
            )
    
    def check_device_info(self) -> CheckResult:
        """Check device information."""
        device = DeviceModule(self.client)
        info = device.get_device_info()
        
        details = {
            "model": info.model,
            "android_version": info.android_version,
            "api_level": info.api_level,
            "security_patch": info.security_patch,
            "build_fingerprint": info.build_fingerprint,
            "is_rooted": device.is_rooted(),
        }
        
        # Check security patch age
        patch_age_days = 0
        if info.security_patch:
            try:
                patch_date = datetime.strptime(info.security_patch, "%Y-%m-%d")
                patch_age_days = (datetime.now() - patch_date).days
            except ValueError:
                pass
        
        max_age = self.config.thresholds['security']['max_patch_age_days']
        status = "pass"
        message = f"Device: {info.model}, Android {info.android_version}"
        
        if patch_age_days > max_age:
            status = "warning"
            message += f" - Security patch is {patch_age_days} days old (>{max_age} days)"
        else:
            message += f" - Security patch: {info.security_patch} ({patch_age_days} days old)"
        
        details["patch_age_days"] = patch_age_days
        
        return CheckResult(name="device_info", status=status, message=message, details=details)
    
    def check_battery(self) -> CheckResult:
        """Check battery health."""
        battery = BatteryModule(self.client)
        info = battery.get_battery_info()
        
        thresholds = self.config.thresholds['battery']
        
        details = {
            "level_percent": info.level,
            "health": info.health.value,
            "status": info.status.value,
            "temperature_c": info.temperature_c,
            "voltage_mv": info.voltage_mv,
            "current_ma": info.current_ma,
            "charge_cycles": info.charge_cycles,
            "capacity_mah": info.capacity_mah,
            "technology": info.technology,
        }
        
        issues = []
        
        if info.level < thresholds['min_level_percent']:
            issues.append(f"Low battery: {info.level}% (<{thresholds['min_level_percent']}%)")
        
        if info.temperature_c > thresholds['max_temperature_c']:
            issues.append(f"High temperature: {info.temperature_c:.1f}°C (>{thresholds['max_temperature_c']}°C)")
        
        if thresholds['min_health_good'] and info.health != BatteryHealth.GOOD:
            issues.append(f"Battery health: {info.health.value} (not GOOD)")
        
        if info.charge_cycles is not None and info.charge_cycles >= thresholds['charge_cycles_warning']:
            issues.append(f"High charge cycles: {info.charge_cycles} (>{thresholds['charge_cycles_warning']})")
        
        status = "pass" if not issues else "warning"
        message = "Battery OK" if not issues else "; ".join(issues)
        
        return CheckResult(name="battery", status=status, message=message, details=details)
    
    def check_storage(self) -> CheckResult:
        """Check storage usage."""
        storage = StorageModule(self.client)
        partitions = storage.get_storage_info()
        
        thresholds = self.config.thresholds['storage']
        
        details = {
            "partitions": [],
            "total_used_gb": 0,
            "total_free_gb": 0,
            "total_size_gb": 0,
        }
        
        issues = []
        
        for part in partitions:
            part_info = {
                "mount_point": part.mount_point,
                "total_gb": part.total_gb,
                "used_gb": part.used_gb,
                "free_gb": part.free_gb,
                "usage_percent": part.usage_percent,
                "filesystem": part.filesystem,
            }
            details["partitions"].append(part_info)
            details["total_used_gb"] += part.used_gb
            details["total_free_gb"] += part.free_gb
            details["total_size_gb"] += part.total_gb
            
            if part.usage_percent > thresholds['max_usage_percent']:
                issues.append(f"{part.mount_point}: {part.usage_percent:.1f}% used (>{thresholds['max_usage_percent']}%)")
            
            if part.free_gb < thresholds['min_free_gb']:
                issues.append(f"{part.mount_point}: {part.free_gb:.1f}GB free (<{thresholds['min_free_gb']}GB)")
        
        # Check for large files
        large_files = storage.find_large_files(thresholds['large_file_threshold_mb'] / 1024)
        if large_files:
            details["large_files_count"] = len(large_files)
            issues.append(f"Found {len(large_files)} files >{thresholds['large_file_threshold_mb']}MB")
        
        status = "pass" if not issues else "warning"
        message = "Storage OK" if not issues else "; ".join(issues)
        
        return CheckResult(name="storage", status=status, message=message, details=details)

    def check_thermal(self) -> CheckResult:
        """Check thermal status."""
        thermal = ThermalModule(self.client)
        info = thermal.get_thermal_info()

        thresholds = self.config.thresholds['thermal']

        details = {
            "zones": [],
            "cpu_throttling": info.cpu_throttled,
            "gpu_throttling": info.gpu_throttled,
            "overall_status": info.overall_status.value,
        }

        issues = []

        for zone in info.zones:
            zone_info = {
                "name": zone.name,
                "temp_c": zone.temp_c,
                "type": zone.type,
            }
            details["zones"].append(zone_info)

            if zone.temp_c > thresholds['max_zone_temp_c']:
                issues.append(f"Zone {zone.name}: {zone.temp_c:.1f}°C (>{thresholds['max_zone_temp_c']}°C)")

        if info.cpu_throttled:
            issues.append("CPU throttling active")
        if info.gpu_throttled:
            issues.append("GPU throttling active")

        status = "pass" if not issues else "warning"
        message = "Thermal OK" if not issues else "; ".join(issues)

        return CheckResult(name="thermal", status=status, message=message, details=details)

    def check_network(self) -> CheckResult:
        """Check network connectivity."""
        network = NetworkModule(self.client)
        info = network.get_network_info()
        
        thresholds = self.config.thresholds['network']
        
        details = {
            "wifi": {
                "connected": info.wifi_connected,
                "ssid": info.wifi_ssid,
                "signal_dbm": info.wifi_signal_dbm,
                "frequency_mhz": info.wifi_frequency_mhz,
                "ip_address": info.wifi_ip,
            },
            "mobile": {
                "connected": info.mobile_connected,
                "operator": info.mobile_operator,
                "signal_dbm": info.mobile_signal_dbm,
                "network_type": info.mobile_network_type,
                "ip_address": info.mobile_ip,
            },
            "dns_servers": info.dns_servers,
            "gateway": info.gateway,
            "internet_reachable": info.internet_reachable,
        }
        
        issues = []
        
        if info.wifi_connected:
            if info.wifi_signal_dbm and info.wifi_signal_dbm < thresholds['min_signal_dbm']:
                issues.append(f"Weak Wi-Fi signal: {info.wifi_signal_dbm} dBm (<{thresholds['min_signal_dbm']})")
        elif info.mobile_connected:
            if info.mobile_signal_dbm and info.mobile_signal_dbm < thresholds['min_signal_dbm']:
                issues.append(f"Weak mobile signal: {info.mobile_signal_dbm} dBm (<{thresholds['min_signal_dbm']})")
        else:
            issues.append("No network connection")
        
        if not info.internet_reachable:
            issues.append("Internet not reachable")
        
        # Test DNS resolution
        try:
            dns_ok = network.test_dns_resolution("google.com", timeout=thresholds['dns_timeout_ms'] / 1000)
            if not dns_ok:
                issues.append("DNS resolution failed")
        except Exception:
            issues.append("DNS test failed")
        
        status = "pass" if not issues else "warning"
        message = "Network OK" if not issues else "; ".join(issues)
        
        return CheckResult(name="network", status=status, message=message, details=details)
    
    def check_logcat(self) -> CheckResult:
        """Check logcat for crashes/ANRs with false positive filtering."""
        logcat = LogcatModule(self.client)
        
        thresholds = self.config.thresholds['logcat']
        logcat_config = thresholds.get('filter', {})
        
        # Configure filtering
        filter_samsung = logcat_config.get('filter_samsung', True)
        filter_third_party = logcat_config.get('filter_third_party', True)
        filter_verbose = logcat_config.get('filter_verbose', True)
        filter_benign = logcat_config.get('filter_benign', True)
        
        details = {}
        issues = []
        
        # Get logs with filtering stats
        lines_to_check = 500  # Check more lines for better coverage
        result = logcat.get_logs_with_stats(
            lines=lines_to_check,
            filter_samsung=filter_samsung,
            filter_third_party=filter_third_party,
            filter_verbose=filter_verbose,
            filter_benign=filter_benign,
        )
        
        filtered_logs = result["filtered_logs"]
        stats = result["stats"]
        
        details["filter_stats"] = stats
        details["false_positives_count"] = stats["false_positives"]
        details["false_positive_by_tag"] = stats.get("false_positive_by_tag", {})
        
        # Check for crashes (filtered)
        crashes = [log for log in filtered_logs 
                   if log.level in (LogLevel.ERROR, LogLevel.FATAL) 
                   and any(k in log.tag.lower() for k in ("runtime", "exception", "crash", "fatal"))]
        details["crashes_count"] = len(crashes)
        details["crashes"] = [
            {"tag": c.tag, "message": c.message[:200], "timestamp": c.timestamp.isoformat()}
            for c in crashes[:10]
        ]
        
        if len(crashes) > thresholds['max_crashes_per_hour']:
            issues.append(f"High crash rate: {len(crashes)} crashes (>{thresholds['max_crashes_per_hour']}/hr)")
        
        # Check for ANRs (filtered)
        anrs = [log for log in filtered_logs
                if log.level in (LogLevel.WARN, LogLevel.ERROR, LogLevel.FATAL)
                and ("anr" in log.tag.lower() or "anr" in log.message.lower())]
        details["anrs_count"] = len(anrs)
        details["anrs"] = [
            {"tag": a.tag, "message": a.message[:200], "timestamp": a.timestamp.isoformat()}
            for a in anrs[:10]
        ]
        
        if len(anrs) > thresholds['max_anrs_per_hour']:
            issues.append(f"High ANR rate: {len(anrs)} ANRs (>{thresholds['max_anrs_per_hour']}/hr)")
        
        # Check for permission denials (filtered)
        denials = [log for log in filtered_logs
                   if log.level in (LogLevel.WARN, LogLevel.ERROR)
                   and "permission" in log.message.lower() and "denied" in log.message.lower()]
        details["permission_denials_count"] = len(denials)
        
        # Include filter effectiveness info
        if stats["filter_rate"] > 0.5:
            issues.append(f"High false positive rate: {stats['filter_rate']:.0%} of logs filtered ({stats['false_positives']}/{stats['total']})")
        
        status = "pass" if not issues else "warning"
        message = "Logcat OK" if not issues else "; ".join(issues)
        
        return CheckResult(name="logcat", status=status, message=message, details=details)
    
    def check_apps(self) -> CheckResult:
        """Check app status."""
        apps = AppsModule(self.client)
        
        details = {}
        
        # Get running apps
        running = apps.get_running_apps()
        details["running_apps_count"] = len(running)
        details["running_apps"] = running[:20]
        
        # Check for apps with high resource usage (if we can get that)
        # This is limited without root
        
        status = "pass"
        message = f"Apps OK - {len(running)} running"
        
        return CheckResult(name="apps", status=status, message=message, details=details)
    
    def run_all_checks(self) -> list[CheckResult]:
        """Run all health checks."""
        self._create_client()
        
        checks = [
            ("device_info", self.check_device_info),
            ("battery", self.check_battery),
            ("storage", self.check_storage),
            ("thermal", self.check_thermal),
            ("network", self.check_network),
            ("logcat", self.check_logcat),
            ("apps", self.check_apps),
        ]
        
        if self.config.advanced.get('parallel_checks', True):
            # Run checks in parallel using asyncio
            async def run_async():
                tasks = []
                for name, func in checks:
                    tasks.append(asyncio.to_thread(self._run_check, name, func))
                return await asyncio.gather(*tasks)
            
            self.results = asyncio.run(run_async())
        else:
            for name, func in checks:
                self.results.append(self._run_check(name, func))
        
        return self.results
    
    def generate_report(self) -> HealthReport:
        """Generate comprehensive health report."""
        device = DeviceModule(self.client)
        battery = BatteryModule(self.client)
        storage = StorageModule(self.client)
        network = NetworkModule(self.client)
        thermal = ThermalModule(self.client)
        
        device_info = device.get_device_info()
        battery_info = battery.get_battery_info()
        storage_info = storage.get_storage_info()
        network_info = network.get_network_info()
        thermal_info = thermal.get_thermal_info()
        
        # Determine overall health
        has_fail = any(r.status == "fail" for r in self.results)
        has_error = any(r.status == "error" for r in self.results)
        has_warning = any(r.status == "warning" for r in self.results)
        
        if has_fail or has_error:
            overall = "critical"
        elif has_warning:
            overall = "warning"
        else:
            overall = "healthy"
        
        # Build summary
        summary_parts = []
        for r in self.results:
            if r.status != "pass":
                summary_parts.append(f"{r.name}: {r.message}")
        
        summary = "All checks passed" if not summary_parts else "; ".join(summary_parts)
        
        report = HealthReport(
            timestamp=self.start_time,
            device=device_info,
            battery=battery_info,
            storage=storage_info,
            network=network_info,
            thermal=thermal_info,
            checks=[asdict(r) for r in self.results],
            overall_status=overall,
            summary_text=summary,
        )
        
        return report
    
    def _make_writable(self, file_path: Path) -> None:
        """Remove read-only attribute on Windows to allow writing."""
        import platform
        if platform.system() == "Windows" and file_path.exists():
            try:
                import stat
                file_path.chmod(file_path.stat().st_mode | stat.S_IWRITE)
            except Exception:
                pass

    def _validate_template(self, template: str) -> None:
        """Reject report-path templates containing '..' segments outright."""
        if ".." in Path(template).parts:
            raise ValueError(f"report path template may not contain '..': {template}")

    def save_reports(self, report: HealthReport) -> None:
        """Save reports to files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        date_str = datetime.now().strftime("%Y-%m-%d")

        # JSON report
        if self.config.output.get('json_report', {}).get('enabled', True):
            template = self.config.output['json_report']['path']
            self._validate_template(template)
            json_file = self._report_file(template, date_str, timestamp)
            json_file.parent.mkdir(parents=True, exist_ok=True)

            # Remove read-only attribute on Windows
            self._make_writable(json_file)

            json_file.write_text(json.dumps(asdict(report), indent=2, default=str), encoding='utf-8')
            self.logger.info(f"JSON report saved to {json_file}")

        # Summary report
        if self.config.output.get('summary_report', {}).get('enabled', True):
            template = self.config.output['summary_report']['path']
            self._validate_template(template)
            summary_file = self._report_file(template, date_str, timestamp)
            summary_file.parent.mkdir(parents=True, exist_ok=True)

            # Remove read-only attribute on Windows
            self._make_writable(summary_file)

            summary_file.write_text(self.format_summary(report), encoding='utf-8')
            self.logger.info(f"Summary report saved to {summary_file}")

        # Cleanup old reports
        self._cleanup_old_reports()

    def _report_file(self, template: str, date_str: str, timestamp: str) -> Path:
        """Build a report path from a config template.

        The diagnostics package directory is the fixed root: the template is
        resolved against it and must land inside. ``..`` segments or absolute
        paths pointing elsewhere raise PathEscapeError.
        """
        from phone.paths import confined_path

        substituted = str(template).replace("{{date}}", date_str).replace("{{timestamp}}", timestamp)
        return confined_path(self.output_root, self.output_root / substituted)

    def _cleanup_old_reports(self) -> None:
        """Remove reports older than retention_days."""
        retention = self.config.output.get('retention_days', 30)
        cutoff = datetime.now() - timedelta(days=retention)

        from phone.paths import confined_path

        reports_root = (self.output_root / "reports").resolve()
        for pattern in ["health_report_*.json", "summary_*.txt"]:
            for file in reports_root.glob(pattern):
                try:
                    # Only ever delete inside the reports root
                    confined_path(reports_root, file)
                    # Extract date from filename
                    mtime = datetime.fromtimestamp(file.stat().st_mtime)
                    if mtime < cutoff:
                        file.unlink()
                        self.logger.info(f"Removed old report: {file}")
                except Exception:
                    pass
    
    def format_summary(self, report: HealthReport) -> str:
        """Format human-readable summary."""
        lines = [
            "=" * 60,
            f"Galaxy S22+ Health Report - {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 60,
            "",
            f"Device: {report.device.model} (Android {report.device.android_version})",
            f"Security Patch: {report.device.security_patch}",
            f"Overall Status: {report.overall_status.upper()}",
            "",
            f"Battery: {report.battery.level}% - {report.battery.health.value} - {report.battery.temperature_c:.1f}°C",
            f"  Status: {report.battery.status.value}",
            f"  Voltage: {report.battery.voltage_mv}mV, Current: {report.battery.current_ma or 'N/A'}mA",
            f"  Charge Cycles: {report.battery.charge_cycles or 'N/A'}",
            "",
            "Storage:",
        ]
        
        for part in report.storage:
            lines.append(f"  {part.mount_point}: {part.usage_percent:.1f}% used ({part.free_gb:.1f}GB free)")
        
        lines.extend([
            "",
            f"Network: {'Wi-Fi' if report.network.wifi_connected else 'Mobile' if report.network.mobile_connected else 'None'}",
            f"  Internet: {'Yes' if report.network.internet_reachable else 'No'}",
            f"  Gateway: {report.network.gateway}",
            "",
            f"Thermal: {report.thermal.status.value}",
            f"  CPU Throttling: {'Yes' if report.thermal.cpu_throttled else 'No'}",
            f"  GPU Throttling: {'Yes' if report.thermal.gpu_throttled else 'No'}",
        ])
        
        for zone in report.thermal.zones:
            if zone.temp_c > 0:
                lines.append(f"  {zone.name}: {zone.temp_c:.1f}°C ({zone.type})")
        
        lines.extend([
            "",
            "Check Results:",
        ])
        
        for check in report.checks:
            status_symbol = {"pass": "✓", "warning": "⚠", "fail": "✗", "error": "✗"}.get(check['status'], "?")
            lines.append(f"  {status_symbol} {check['name']}: {check['message']} ({check['duration_ms']:.1f}ms)")
        
        lines.extend([
            "",
            f"Summary: {report.summary}",
            "=" * 60,
        ])
        
        return "\n".join(lines)
    
    def send_notifications(self, report: HealthReport) -> None:
        """Send notifications based on configuration."""
        has_issues = report.overall_status != "healthy"
        only_on_issues = self.config.notifications.get('desktop', {}).get('only_on_issues', True)
        
        if only_on_issues and not has_issues:
            return
        
        # Desktop notification (Windows)
        if self.config.notifications.get('desktop', {}).get('enabled', True):
            self._send_desktop_notification(report)
        
        # Webhook
        if self.config.notifications.get('webhook', {}).get('enabled', False):
            self._send_webhook(report)
        
        # Email
        if self.config.notifications.get('email', {}).get('enabled', False):
            self._send_email(report)
    
    def _send_desktop_notification(self, report: HealthReport) -> None:
        """Send Windows toast notification."""
        try:
            import winrt.windows.ui.notifications as notifications
            import winrt.windows.data.xml.dom as dom
            
            # Create toast XML
            template = f"""
            <toast>
                <visual>
                    <binding template="ToastGeneric">
                        <text>Galaxy S22+ Health Check</text>
                        <text>{report.summary}</text>
                    </binding>
                </visual>
            </toast>
            """
            
            xml_doc = dom.XmlDocument()
            xml_doc.load_xml(template)
            toast = notifications.ToastNotification(xml_doc)
            notifier = notifications.ToastNotificationManager.create_toast_notifier("Galaxy S22+ Diagnostics")
            notifier.show(toast)
            
            self.logger.info("Desktop notification sent")
        except Exception as e:
            self.logger.warning(f"Failed to send desktop notification: {e}")
    
    def _send_webhook(self, report: HealthReport) -> None:
        """Send webhook notification."""
        webhook = self.config.notifications['webhook']
        url = webhook.get('url')
        
        if not url:
            return
        
        try:
            import requests
            
            # Determine color based on status
            colors = {"healthy": 0x00FF00, "warning": 0xFFFF00, "critical": 0xFF0000}
            color = colors.get(report.overall_status, 0x808080)
            
            # Build payload from template
            template = webhook.get('template', '{}')
            payload_str = template.replace("{{device_name}}", report.device.model)
            payload_str = payload_str.replace("{{summary}}", report.summary)
            payload_str = payload_str.replace("{{color}}", str(color))
            payload_str = payload_str.replace("{{battery_status}}", f"{report.battery.level}% {report.battery.health.value}")
            payload_str = payload_str.replace("{{storage_status}}", f"{report.storage[0].usage_percent:.1f}% used" if report.storage else "N/A")
            payload_str = payload_str.replace("{{thermal_status}}", report.thermal.overall_status.value)
            payload_str = payload_str.replace("{{network_status}}", "Connected" if report.network.internet_reachable else "Disconnected")
            
            payload = json.loads(payload_str)
            
            headers = webhook.get('headers', {})
            headers.setdefault('Content-Type', 'application/json')
            
            response = requests.request(
                webhook.get('method', 'POST'),
                url,
                json=payload,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            self.logger.info("Webhook notification sent")
        except Exception as e:
            self.logger.warning(f"Failed to send webhook: {e}")
    
    def _send_email(self, report: HealthReport) -> None:
        """Send email notification."""
        email_config = self.config.notifications['email']
        
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            msg = MIMEMultipart()
            msg['From'] = email_config['from_address']
            msg['To'] = ", ".join(email_config['to_addresses'])
            msg['Subject'] = f"Galaxy S22+ Health Check - {report.overall_status.upper()}"
            
            body = self.format_summary(report)
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port']) as server:
                server.starttls()
                server.login(email_config['username'], email_config['password'])
                server.send_message(msg)
            
            self.logger.info("Email notification sent")
        except Exception as e:
            self.logger.warning(f"Failed to send email: {e}")
    
    def run(self) -> int:
        """Run diagnostics and return exit code."""
        self.logger.info("Starting Galaxy S22+ diagnostics")
        self.start_time = datetime.now()
        
        try:
            self.run_all_checks()
            report = self.generate_report()
            self.save_reports(report)
            self.send_notifications(report)
            
            # Print summary
            print(self.format_summary(report))
            
            # Return exit code based on status
            if report.overall_status == "critical":
                return 2
            elif report.overall_status == "warning":
                return 1
            return 0
            
        except Exception as e:
            self.logger.error(f"Diagnostics failed: {e}", exc_info=True)
            return 3

    async def run_async(self) -> int:
        """Run diagnostics asynchronously (for use within existing event loop)."""
        self.logger.info("Starting Galaxy S22+ diagnostics (async)")
        self.start_time = datetime.now()
        
        try:
            # Create ADB client
            self._create_client()
            
            # Run checks directly without asyncio.run()
            if self.config.advanced.get('parallel_checks', True):
                tasks = []
                for name, func in [
                    ("device_info", self.check_device_info),
                    ("battery", self.check_battery),
                    ("storage", self.check_storage),
                    ("thermal", self.check_thermal),
                    ("network", self.check_network),
                    ("logcat", self.check_logcat),
                    ("apps", self.check_apps),
                ]:
                    tasks.append(asyncio.to_thread(self._run_check, name, func))
                await asyncio.gather(*tasks)
            else:
                for name, func in [
                    ("device_info", self.check_device_info),
                    ("battery", self.check_battery),
                    ("storage", self.check_storage),
                    ("thermal", self.check_thermal),
                    ("network", self.check_network),
                    ("logcat", self.check_logcat),
                    ("apps", self.check_apps),
                ]:
                    self.results.append(self._run_check(name, func))
            
            report = self.generate_report()
            self.save_reports(report)
            self.send_notifications(report)
            
            # Print summary
            print(self.format_summary(report))
            
            # Return exit code based on status
            if report.overall_status == "critical":
                return 2
            elif report.overall_status == "warning":
                return 1
            return 0
            
        except Exception as e:
            self.logger.error(f"Diagnostics failed: {e}", exc_info=True)
            return 3


def main():
    """Main entry point."""
    config_path = Path(__file__).parent / "config.yaml"
    
    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        return 1
    
    runner = DiagnosticsRunner(config_path)
    return runner.run()


if __name__ == "__main__":
    sys.exit(main())