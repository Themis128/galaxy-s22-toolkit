"""Unit tests for logcat module."""

from phone.logcat import FilterConfig, LogcatModule
from phone.models import LogEntry, LogLevel


class TestLogcatModule:
    """Tests for LogcatModule."""

    def test_get_logs(self, mock_adb_client, mock_log_entries):
        """Test getting logcat logs."""
        module = LogcatModule(mock_adb_client)
        logs = module.get_logs(lines=10)

        assert len(logs) == 10
        assert all(isinstance(log, LogEntry) for log in logs)

    def test_get_errors(self, mock_adb_client):
        """Test filtering error logs."""
        module = LogcatModule(mock_adb_client)
        errors = module.get_errors()

        # Should have multiple E level entries
        assert len(errors) >= 4
        assert all(log.level == LogLevel.ERROR for log in errors)

    def test_get_warnings(self, mock_adb_client):
        """Test filtering warning logs."""
        module = LogcatModule(mock_adb_client)
        warnings = module.get_warnings()

        assert len(warnings) >= 2
        assert all(log.level == LogLevel.WARN for log in warnings)

    def test_get_crashes(self, mock_adb_client):
        """Test detecting crashes."""
        module = LogcatModule(mock_adb_client)
        crashes = module.get_crashes()

        # Should detect AndroidRuntime FATAL EXCEPTION and NullPointerException
        assert len(crashes) >= 2
        crash_messages = " ".join(c.message for c in crashes)
        assert "FATAL EXCEPTION" in crash_messages or "NullPointerException" in crash_messages

    def test_get_anrs(self, mock_adb_client):
        """Test detecting ANRs."""
        module = LogcatModule(mock_adb_client)
        anrs = module.get_anrs()

        assert len(anrs) >= 1
        anr_messages = " ".join(a.message for a in anrs)
        assert "ANR" in anr_messages

    def test_grep_logs(self, mock_adb_client):
        """Test searching logs for pattern."""
        module = LogcatModule(mock_adb_client)
        matches = module.grep_logs("timeout")

        assert len(matches) >= 1
        assert any("timeout" in m.message.lower() for m in matches)

    def test_find_crashes_in_buffer(self, mock_adb_client):
        """Test finding crashes in buffer."""
        module = LogcatModule(mock_adb_client)
        crashes = module.find_crashes_in_buffer()

        assert len(crashes) >= 1

    def test_find_anrs_in_buffer(self, mock_adb_client):
        """Test finding ANRs in buffer."""
        module = LogcatModule(mock_adb_client)
        anrs = module.find_anrs_in_buffer()

        assert len(anrs) >= 1

    def test_find_permission_denials(self, mock_adb_client):
        """Test finding permission denials."""
        module = LogcatModule(mock_adb_client)
        denials = module.find_permission_denials()

        assert len(denials) >= 1
        assert any("Permission denied" in d.message for d in denials)

    def test_find_native_crashes(self, mock_adb_client):
        """Test finding native crashes."""
        module = LogcatModule(mock_adb_client)
        native = module.find_native_crashes()

        # Native crashes typically have SIGSEGV, SIGABRT in message
        assert isinstance(native, list)

    def test_get_app_logs(self, mock_adb_client):
        """Test getting logs for specific app."""
        module = LogcatModule(mock_adb_client)
        logs = module.get_app_logs("com.example.app")

        # With package filter, would only return matching logs
        assert isinstance(logs, list)

    def test_clear_logs(self, mock_adb_client):
        """Test clearing logcat buffer."""
        module = LogcatModule(mock_adb_client)
        result = module.clear_logs()
        assert result is True

    def test_get_log_stats(self, mock_adb_client):
        """Test getting log statistics."""
        module = LogcatModule(mock_adb_client)
        stats = module.get_log_stats()

        assert "total_lines" in stats
        assert "by_level" in stats
        assert "by_tag" in stats
        assert stats["total_lines"] >= 10

    def test_get_top_tags(self, mock_adb_client):
        """Test getting most frequent log tags."""
        module = LogcatModule(mock_adb_client)
        tags = module.get_top_tags(limit=5)

        assert len(tags) <= 5
        assert all(isinstance(tag, tuple) and len(tag) == 2 for tag in tags)
        assert tags[0][1] >= tags[-1][1]  # Sorted by count descending

    def test_parse_brief_format_logs(self, mock_adb_client):
        """Test parsing brief format logs."""
        mock_adb_client.execute.return_value = """D/Tag1(100): Message 1
E/Tag2(200): Error message
W/Tag3(300): Warning message
"""
        module = LogcatModule(mock_adb_client)
        logs = module.get_logs(format="brief")

        assert len(logs) == 3
        assert logs[0].level == LogLevel.DEBUG
        assert logs[1].level == LogLevel.ERROR
        assert logs[2].level == LogLevel.WARN

    def test_parse_threadtime_format_logs(self, mock_adb_client):
        """Test parsing threadtime format logs (default)."""
        module = LogcatModule(mock_adb_client)
        logs = module.get_logs(format="threadtime")

        assert len(logs) == 10
        assert logs[0].level == LogLevel.DEBUG
        assert logs[0].tag == "MainActivity"
        assert logs[4].level == LogLevel.ERROR
        assert logs[4].tag == "AndroidRuntime"


class TestFilterConfig:
    """Tests for FilterConfig dataclass."""

    def test_default_filter_config(self):
        """Test default filter configuration has expected patterns."""
        config = FilterConfig()

        # Samsung tag patterns
        assert len(config.samsung_tag_patterns) > 0
        assert any("samsung" in p.lower() for p in config.samsung_tag_patterns)
        assert any("sec" in p.lower() for p in config.samsung_tag_patterns)

        # Third-party tag patterns
        assert len(config.third_party_tag_patterns) > 0
        assert any("facebook" in p.lower() for p in config.third_party_tag_patterns)
        assert any("google" in p.lower() for p in config.third_party_tag_patterns)
        assert any("analytics" in p.lower() for p in config.third_party_tag_patterns)

        # Verbose message patterns
        assert len(config.verbose_message_patterns) > 0
        assert any("verbose" in p.lower() for p in config.verbose_message_patterns)
        assert any("debug" in p.lower() for p in config.verbose_message_patterns)

        # Benign message patterns
        assert len(config.benign_message_patterns) > 0
        assert any("dex2oat" in p.lower() for p in config.benign_message_patterns)
        assert any("selinux" in p.lower() for p in config.benign_message_patterns)


class TestFalsePositiveFiltering:
    """Tests for false positive filtering functionality."""

    def test_filter_samsung_tags(self, mock_adb_client):
        """Test filtering Samsung system verbose logs."""
        # Samsung logs at ERROR level that are just verbose logging
        samsung_logs = [
            LogEntry(
                timestamp="2024-01-01T12:00:00.000",
                level=LogLevel.ERROR,
                pid=100,
                tid=100,
                tag="SamsungHealth",
                message="Verbose error from Samsung Health service",
                raw="01-01 12:00:00.000  100  100 E SamsungHealth: Verbose error from Samsung Health service",
            ),
            LogEntry(
                timestamp="2024-01-01T12:00:01.000",
                level=LogLevel.ERROR,
                pid=101,
                tid=101,
                tag="SamsungCamera",
                message="Camera service verbose log",
                raw="01-01 12:00:01.000  101  101 E SamsungCamera: Camera service verbose log",
            ),
            # Real error that should NOT be filtered
            LogEntry(
                timestamp="2024-01-01T12:00:02.000",
                level=LogLevel.ERROR,
                pid=102,
                tid=102,
                tag="AndroidRuntime",
                message="FATAL EXCEPTION: main",
                raw="01-01 12:00:02.000  102  102 E AndroidRuntime: FATAL EXCEPTION: main",
            ),
        ]
        module = LogcatModule(mock_adb_client)
        filtered, false_positives = module.filter_false_positives(
            samsung_logs,
            filter_samsung=True,
            filter_third_party=False,
            filter_verbose=False,
            filter_benign=False,
        )

        # SamsungHealth and SamsungCamera should be filtered
        assert len(false_positives) == 2
        assert any(log.tag == "SamsungHealth" for log in false_positives)
        assert any(log.tag == "SamsungCamera" for log in false_positives)

        # AndroidRuntime crash should NOT be filtered
        assert len(filtered) == 1
        assert filtered[0].tag == "AndroidRuntime"

    def test_filter_third_party_tags(self, mock_adb_client):
        """Test filtering third-party app spam."""
        third_party_logs = [
            LogEntry(
                timestamp="2024-01-01T12:00:00.000",
                level=LogLevel.ERROR,
                pid=100,
                tid=100,
                tag="com.facebook.katana",
                message="Analytics event sent",
                raw="01-01 12:00:00.000  100  100 E com.facebook.katana: Analytics event sent",
            ),
            LogEntry(
                timestamp="2024-01-01T12:00:01.000",
                level=LogLevel.WARN,
                pid=101,
                tid=101,
                tag="com.google.android.gms",
                message="Location update received",
                raw="01-01 12:00:01.000  101  101 W com.google.android.gms: Location update received",
            ),
            # Real error that should NOT be filtered
            LogEntry(
                timestamp="2024-01-01T12:00:02.000",
                level=LogLevel.ERROR,
                pid=102,
                tid=102,
                tag="com.myapp",
                message="Database connection failed",
                raw="01-01 12:00:02.000  102  102 E com.myapp: Database connection failed",
            ),
        ]
        module = LogcatModule(mock_adb_client)
        filtered, false_positives = module.filter_false_positives(
            third_party_logs,
            filter_samsung=False,
            filter_third_party=True,
            filter_verbose=False,
            filter_benign=False,
        )

        # Facebook and Google Play Services should be filtered
        assert len(false_positives) >= 2
        assert any("facebook" in log.tag for log in false_positives)
        assert any("google" in log.tag for log in false_positives)

        # MyApp should NOT be filtered
        assert len(filtered) == 1
        assert filtered[0].tag == "com.myapp"

    def test_filter_verbose_messages(self, mock_adb_client):
        """Test filtering verbose/debug messages at ERROR/WARN level."""
        verbose_logs = [
            LogEntry(
                timestamp="2024-01-01T12:00:00.000",
                level=LogLevel.ERROR,
                pid=100,
                tid=100,
                tag="SomeTag",
                message="This is a verbose debug message",
                raw="01-01 12:00:00.000  100  100 E SomeTag: This is a verbose debug message",
            ),
            LogEntry(
                timestamp="2024-01-01T12:00:01.000",
                level=LogLevel.WARN,
                pid=101,
                tid=101,
                tag="AnotherTag",
                message="Debug: entering function xyz",
                raw="01-01 12:00:01.000  101  101 W AnotherTag: Debug: entering function xyz",
            ),
            # Real error without verbose keywords
            LogEntry(
                timestamp="2024-01-01T12:00:02.000",
                level=LogLevel.ERROR,
                pid=102,
                tid=102,
                tag="RealError",
                message="Failed to connect to server",
                raw="01-01 12:00:02.000  102  102 E RealError: Failed to connect to server",
            ),
        ]
        module = LogcatModule(mock_adb_client)
        filtered, false_positives = module.filter_false_positives(
            verbose_logs,
            filter_samsung=False,
            filter_third_party=False,
            filter_verbose=True,
            filter_benign=False,
        )

        # Verbose and debug messages should be filtered
        assert len(false_positives) >= 2

        # Real error should NOT be filtered
        assert len(filtered) == 1
        assert filtered[0].tag == "RealError"

    def test_filter_benign_messages(self, mock_adb_client):
        """Test filtering known benign warnings."""
        benign_logs = [
            LogEntry(
                timestamp="2024-01-01T12:00:00.000",
                level=LogLevel.WARN,
                pid=100,
                tid=100,
                tag="dex2oat",
                message="Failed to find provider info for dex2oat",
                raw="01-01 12:00:00.000  100  100 W dex2oat: Failed to find provider info for dex2oat",
            ),
            LogEntry(
                timestamp="2024-01-01T12:00:01.000",
                level=LogLevel.WARN,
                pid=101,
                tid=101,
                tag="SELinux",
                message="Failed to find provider for SELinux",
                raw="01-01 12:00:01.000  101  101 W SELinux: Failed to find provider for SELinux",
            ),
            # Real warning that should NOT be filtered
            LogEntry(
                timestamp="2024-01-01T12:00:02.000",
                level=LogLevel.WARN,
                pid=102,
                tid=102,
                tag="BatteryStats",
                message="Battery level critically low",
                raw="01-01 12:00:02.000  102  102 W BatteryStats: Battery level critically low",
            ),
        ]
        module = LogcatModule(mock_adb_client)
        filtered, false_positives = module.filter_false_positives(
            benign_logs,
            filter_samsung=False,
            filter_third_party=False,
            filter_verbose=False,
            filter_benign=True,
        )

        # dex2oat and SELinux messages should be filtered (match "Failed to find provider")
        assert len(false_positives) >= 2

        # BatteryStats should NOT be filtered
        assert len(filtered) == 1
        assert filtered[0].tag == "BatteryStats"

    def test_filter_verbose_only_for_warn_error_fatal(self, mock_adb_client):
        """Test that verbose filtering only applies to WARN/ERROR/FATAL levels."""
        logs = [
            LogEntry(
                timestamp="2024-01-01T12:00:00.000",
                level=LogLevel.DEBUG,
                pid=100,
                tid=100,
                tag="SomeTag",
                message="This is a verbose debug message",
                raw="01-01 12:00:00.000  100  100 D SomeTag: This is a verbose debug message",
            ),
            LogEntry(
                timestamp="2024-01-01T12:00:01.000",
                level=LogLevel.INFO,
                pid=101,
                tid=101,
                tag="AnotherTag",
                message="Debug: entering function xyz",
                raw="01-01 12:00:01.000  101  101 I AnotherTag: Debug: entering function xyz",
            ),
        ]
        module = LogcatModule(mock_adb_client)
        filtered, false_positives = module.filter_false_positives(
            logs,
            filter_samsung=False,
            filter_third_party=False,
            filter_verbose=True,
            filter_benign=False,
        )

        # DEBUG and INFO should NOT be filtered even with verbose keywords
        # because verbose filtering only applies to WARN/ERROR/FATAL
        assert len(false_positives) == 0
        assert len(filtered) == 2

    def test_get_logs_with_stats(self, mock_adb_client):
        """Test get_logs_with_stats returns correct statistics."""
        # Mock logcat output with mixed logs
        mock_adb_client.execute.return_value = """01-01 12:00:00.000  100  100 E SamsungHealth: Verbose error
01-01 12:00:01.000  101  101 E com.facebook.katana: Analytics sent
01-01 12:00:02.000  102  102 E AndroidRuntime: FATAL EXCEPTION: main
01-01 12:00:03.000  103  103 W dex2oat: Failed to find provider info for dex2oat
01-01 12:00:04.000  104  104 W BatteryStats: Battery low
"""
        module = LogcatModule(mock_adb_client)
        result = module.get_logs_with_stats(
            lines=10,
            filter_samsung=True,
            filter_third_party=True,
            filter_verbose=True,
            filter_benign=True,
        )

        assert "filtered_logs" in result
        assert "false_positives" in result
        assert "stats" in result

        stats = result["stats"]
        assert stats["total"] == 5
        assert stats["false_positives"] >= 3  # SamsungHealth, Facebook, dex2oat
        assert stats["filtered"] == stats["total"] - stats["false_positives"]
        assert "false_positive_by_tag" in stats
        assert stats["filter_rate"] > 0

    def test_filtered_errors_excludes_false_positives(self, mock_adb_client):
        """Test get_filtered_errors excludes Samsung/third-party verbose logs."""
        mock_adb_client.execute.return_value = """01-01 12:00:00.000  100  100 E SamsungHealth: Verbose error
01-01 12:00:01.000  101  101 E com.facebook.katana: Analytics sent
01-01 12:00:02.000  102  102 E AndroidRuntime: FATAL EXCEPTION: main
01-01 12:00:03.000  103  103 E com.myapp: Real error occurred
"""
        module = LogcatModule(mock_adb_client)
        filtered = module.get_filtered_errors(
            lines=10,
            filter_samsung=True,
            filter_third_party=True,
            filter_verbose=True,
            filter_benign=True,
        )

        # Should only have AndroidRuntime and MyApp errors
        assert len(filtered) == 2
        tags = [log.tag for log in filtered]
        assert "AndroidRuntime" in tags
        assert "com.myapp" in tags
        assert "SamsungHealth" not in tags
        assert "com.facebook.katana" not in tags

    def test_filtered_warnings_excludes_false_positives(self, mock_adb_client):
        """Test get_filtered_warnings excludes benign warnings."""
        mock_adb_client.execute.return_value = """01-01 12:00:00.000  100  100 W SamsungHealth: Verbose warning
01-01 12:00:01.000  101  101 W dex2oat: Failed to find provider info for dex2oat
01-01 12:00:02.000  102  102 W BatteryStats: Battery critically low
01-01 12:00:03.000  103  103 W com.myapp: Permission denied
"""
        module = LogcatModule(mock_adb_client)
        filtered = module.get_filtered_warnings(
            lines=10,
            filter_samsung=True,
            filter_third_party=True,
            filter_verbose=True,
            filter_benign=True,
        )

        # Should only have BatteryStats and MyApp warnings
        assert len(filtered) == 2
        tags = [log.tag for log in filtered]
        assert "BatteryStats" in tags
        assert "com.myapp" in tags
        assert "SamsungHealth" not in tags
        assert "dex2oat" not in tags
