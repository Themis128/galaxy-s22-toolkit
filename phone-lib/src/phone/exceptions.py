"""Custom exceptions for the phone toolkit."""

from __future__ import annotations

from typing import Any


class PhoneError(Exception):
    """Base exception for all phone toolkit errors."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


class DeviceNotFoundError(PhoneError):
    """Raised when no device is found or device is unauthorized."""

    def __init__(self, serial: str | None = None, message: str | None = None) -> None:
        msg = message or f"Device not found: {serial or 'unknown'}"
        super().__init__(msg, details={"serial": serial})


class DeviceUnauthorizedError(DeviceNotFoundError):
    """Raised when device is connected but unauthorized (need to accept RSA key)."""

    def __init__(self, serial: str | None = None) -> None:
        super().__init__(
            serial, f"Device unauthorized (accept RSA key on phone): {serial or 'unknown'}"
        )


class CommandFailedError(PhoneError):
    """Raised when an ADB command fails."""

    def __init__(
        self,
        command: list[str],
        exit_code: int,
        stdout: str,
        stderr: str,
        message: str | None = None,
    ) -> None:
        msg = message or f"Command failed (exit {exit_code}): {' '.join(command)}"
        super().__init__(
            msg,
            details={
                "command": command,
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr,
            },
        )


class AdbConnectionError(PhoneError):
    """Raised when ADB server connection fails."""

    def __init__(self, message: str, *, adb_path: str | None = None) -> None:
        super().__init__(message, details={"adb_path": adb_path})


class ParseError(PhoneError):
    """Raised when parsing device output fails."""

    def __init__(self, raw_output: str, expected_format: str, message: str | None = None) -> None:
        msg = message or f"Failed to parse output (expected: {expected_format})"
        super().__init__(
            msg, details={"raw_output": raw_output[:500], "expected_format": expected_format}
        )


class TimeoutError(PhoneError):
    """Raised when an operation times out."""

    def __init__(self, operation: str, timeout_seconds: float) -> None:
        super().__init__(
            f"Operation timed out after {timeout_seconds}s: {operation}",
            details={"operation": operation, "timeout_seconds": timeout_seconds},
        )


class FileTransferError(PhoneError):
    """Raised when file push/pull fails."""

    def __init__(self, operation: str, local_path: str, remote_path: str, message: str) -> None:
        super().__init__(
            f"File {operation} failed: {message}",
            details={"operation": operation, "local_path": local_path, "remote_path": remote_path},
        )
