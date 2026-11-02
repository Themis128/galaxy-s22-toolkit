"""Unit tests for ADB client module."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from phone.adb import AdbClient
from phone.exceptions import DeviceNotFoundError


class TestAdbClient:
    """Tests for AdbClient."""

    def test_adb_client_creation(self):
        """Test creating ADB client."""
        client = AdbClient()
        assert client.adb_path is not None
        assert client.timeout == 30.0

    def test_adb_client_with_custom_path(self):
        """Test creating ADB client with custom path."""
        client = AdbClient(adb_path="/custom/path/adb")
        assert client.adb_path == "/custom/path/adb"

    def test_adb_client_with_serial(self):
        """Test creating ADB client with specific serial."""
        client = AdbClient(serial="RFCTA0AEKZP")
        assert client.serial == "RFCTA0AEKZP"

    def test_get_devices(self, mock_adb_client):
        """Test getting device list."""
        devices = mock_adb_client.get_devices()
        assert len(devices) == 1
        assert devices[0]["serial"] == "RFCTA0AEKZP"
        assert devices[0]["state"] == "device"

    def test_execute_command(self, mock_adb_client):
        """Test executing ADB command."""
        result = mock_adb_client.execute("shell", "echo", "test")
        assert isinstance(result, str)

    def test_execute_async_command(self, mock_adb_client):
        """Test executing ADB command asynchronously."""
        result = asyncio.run(mock_adb_client.execute_async("shell", "echo", "test"))
        assert isinstance(result, str)

    def test_shell_command(self, mock_adb_client):
        """Test shell command shortcut."""
        result = mock_adb_client.shell("echo test")
        assert isinstance(result, str)

    def test_push_file(self, mock_adb_client):
        """Test pushing file to device."""
        mock_adb_client.push = MagicMock(return_value=True)
        client = mock_adb_client
        result = client.push("local.txt", "/sdcard/remote.txt")
        assert result is True

    def test_pull_file(self, mock_adb_client):
        """Test pulling file from device."""
        mock_adb_client.pull = MagicMock(return_value=True)
        client = mock_adb_client
        result = client.pull("/sdcard/remote.txt", "local.txt")
        assert result is True

    def test_screenshot(self, mock_adb_client):
        """Test taking screenshot."""
        mock_adb_client.screenshot = MagicMock(return_value="/sdcard/screenshot.png")
        client = mock_adb_client
        path = client.screenshot()
        assert path == "/sdcard/screenshot.png"

    def test_screenrecord(self, mock_adb_client):
        """Test screen recording."""
        mock_adb_client.screenrecord = MagicMock(return_value="/sdcard/video.mp4")
        client = mock_adb_client
        path = client.screenrecord(time_limit=30)
        assert path == "/sdcard/video.mp4"

    def test_forward_port(self, mock_adb_client):
        """Test port forwarding."""
        mock_adb_client.forward = MagicMock(return_value=True)
        client = mock_adb_client
        result = client.forward(8080, 8080)
        assert result is True

    def test_reverse_port(self, mock_adb_client):
        """Test reverse port forwarding."""
        mock_adb_client.reverse = MagicMock(return_value=True)
        client = mock_adb_client
        result = client.reverse(8080, 8080)
        assert result is True

    def test_input_tap(self, mock_adb_client):
        """Test input tap."""
        mock_adb_client.tap = MagicMock(return_value=True)
        client = mock_adb_client
        result = client.tap(500, 1000)
        assert result is True

    def test_input_swipe(self, mock_adb_client):
        """Test input swipe."""
        mock_adb_client.swipe = MagicMock(return_value=True)
        client = mock_adb_client
        result = client.swipe(500, 1500, 500, 500, 300)
        assert result is True

    def test_input_text(self, mock_adb_client):
        """Test input text."""
        mock_adb_client.text = MagicMock(return_value=True)
        client = mock_adb_client
        result = client.text("Hello World")
        assert result is True

    def test_input_keyevent(self, mock_adb_client):
        """Test input keyevent."""
        mock_adb_client.keyevent = MagicMock(return_value=True)
        client = mock_adb_client
        result = client.keyevent("KEYCODE_HOME")
        assert result is True

    def test_logcat_stream(self, mock_adb_client):
        """Test logcat streaming."""
        mock_adb_client.logcat_stream = MagicMock(return_value=None)
        client = mock_adb_client
        client.logcat_stream()
        mock_adb_client.logcat_stream.assert_called_once()

    def test_is_connected(self, mock_adb_client):
        """Test connection check."""
        assert mock_adb_client.is_connected() is True

    def test_device_not_found_error(self):
        """Test DeviceNotFoundError is raised when no devices."""
        client = AdbClient()
        with patch.object(client, 'list_devices', return_value=[]):
            with pytest.raises(DeviceNotFoundError):
                client.get_serial()

    def test_command_timeout_error(self):
        """Test TimeoutError on timeout."""
        from phone.exceptions import TimeoutError as PhoneTimeoutError
        client = AdbClient()
        client._run = MagicMock(side_effect=PhoneTimeoutError("adb shell sleep 60", 1.0))

        with pytest.raises(PhoneTimeoutError):
            client.execute("shell", "sleep", "60", timeout=1.0)

    def test_adb_error_on_failure(self):
        """Test CommandFailedError on command failure."""
        from phone.exceptions import CommandFailedError as PhoneCommandFailedError
        client = AdbClient()
        client._run = MagicMock(side_effect=PhoneCommandFailedError("adb shell invalid_command", 1, "", "error message"))

        with pytest.raises(PhoneCommandFailedError):
            client.execute("shell", "invalid_command")
