"""Storage and partition information via df and other tools."""

from __future__ import annotations

from typing import Any, TypedDict

from .adb import AdbClient
from .models import StorageInfo


class StorageUsage(TypedDict):
    """Storage usage information."""

    total: int
    used: int
    free: int


class StorageModule:
    """Storage information module."""

    def __init__(self, client: AdbClient) -> None:
        self.client = client

    def get_storage_info(self) -> list[StorageInfo]:
        """Get storage information for all partitions."""
        output = self.client.execute("shell", "df")
        return self._parse_df(output)

    def get_storage_usage(self) -> StorageUsage:
        """Get overall storage usage (total, used, free) for the main data partition.

        Returns a StorageUsage TypedDict — access values by key
        (``usage["total"]``), not by attribute."""
        data_storage = self.get_data_storage()
        if data_storage:
            return StorageUsage(
                total=data_storage.total_bytes,
                used=data_storage.used_bytes,
                free=data_storage.free_bytes,
            )
        # Fallback to internal storage
        internal = self.get_internal_storage()
        if internal:
            return StorageUsage(
                total=internal.total_bytes,
                used=internal.used_bytes,
                free=internal.free_bytes,
            )
        # Last resort: sum all partitions
        storages = self.get_storage_info()
        total = sum(s.total_bytes for s in storages)
        used = sum(s.used_bytes for s in storages)
        free = sum(s.free_bytes for s in storages)
        return StorageUsage(total=total, used=used, free=free)

    def _parse_df(self, output: str) -> list[StorageInfo]:
        """Parse df output."""
        storages = []
        lines = output.strip().split("\n")

        # Skip header line
        for line in lines[1:]:
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) < 6:
                continue

            filesystem = parts[0]
            # Convert 1K-blocks to bytes
            try:
                total_kb = int(parts[1])
                used_kb = int(parts[2])
                free_kb = int(parts[3])
            except (ValueError, IndexError):
                continue

            mount_point = parts[5]

            total_bytes = total_kb * 1024
            used_bytes = used_kb * 1024
            free_bytes = free_kb * 1024

            # Guess filesystem type from mount point
            fs_type = self._guess_filesystem(mount_point)

            storages.append(
                StorageInfo(
                    partition=filesystem,
                    total_bytes=total_bytes,
                    used_bytes=used_bytes,
                    free_bytes=free_bytes,
                    filesystem=fs_type,
                    mount_point=mount_point,
                )
            )

        return storages

    def _guess_filesystem(self, mount_point: str) -> str:
        """Guess filesystem type from mount point."""
        if mount_point in ("/", "/system", "/vendor", "/product"):
            return "ext4"
        elif mount_point.startswith("/data"):
            return "f2fs"
        elif mount_point.startswith("/sdcard") or mount_point.startswith("/storage"):
            return "vfat"
        return "unknown"

    def get_data_storage(self) -> StorageInfo | None:
        """Get storage info for /data partition (main user data)."""
        storages = self.get_storage_info()
        for storage in storages:
            if storage.mount_point == "/data":
                return storage
        return None

    def get_internal_storage(self) -> StorageInfo | None:
        """Get storage info for internal storage (/sdcard or /storage/emulated/0)."""
        storages = self.get_storage_info()
        for storage in storages:
            if storage.mount_point in ("/sdcard", "/storage/emulated/0"):
                return storage
        return None

    def get_total_space(self) -> int:
        """Get total space across all partitions in bytes."""
        return sum(s.total_bytes for s in self.get_storage_info())

    def get_used_space(self) -> int:
        """Get used space across all partitions in bytes."""
        return sum(s.used_bytes for s in self.get_storage_info())

    def get_free_space(self) -> int:
        """Get free space across all partitions in bytes."""
        return sum(s.free_bytes for s in self.get_storage_info())

    def find_large_files(
        self, path: str = "/data", min_size_mb: int = 100, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Find large files in a directory."""
        # Use find with size filter
        min_bytes = min_size_mb * 1024 * 1024
        try:
            output = self.client.execute(
                "shell",
                "find",
                path,
                "-type",
                "f",
                "-size",
                f"+{min_bytes}c",
                "-exec",
                "ls",
                "-la",
                "{}",
                ";",
                "2>/dev/null",
                timeout=60.0,
            )
        except Exception:
            return []

        files: list[dict[str, int | float | str]] = []
        for line in output.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) < 9:
                continue
            try:
                size = int(parts[4])
                name = " ".join(parts[8:])
                files.append({"path": name, "size_bytes": size, "size_mb": size / (1024 * 1024)})
            except (ValueError, IndexError):
                continue

        # Sort by size descending
        files.sort(key=lambda x: x["size_bytes"], reverse=True)
        return files[:limit]

    def get_app_storage(self, package_name: str) -> dict[str, int]:
        """Get storage usage for a specific app."""
        try:
            self.client.execute("shell", "dumpsys", "package", package_name)
            # Parse for codePath, dataDir, cacheDir sizes
            # This is a simplified version
            return {
                "data_size": 0,
                "cache_size": 0,
                "code_size": 0,
            }
        except Exception:
            return {"data_size": 0, "cache_size": 0, "code_size": 0}

    def clear_app_cache(self, package_name: str) -> bool:
        """Clear app cache."""
        try:
            self.client.execute("shell", "pm", "clear", "--cache-only", package_name)
            return True
        except Exception:
            return False

    def get_mounted_partitions(self) -> list[dict[str, str]]:
        """Get mounted partitions from /proc/mounts."""
        output = self.client.execute("shell", "cat", "/proc/mounts")
        partitions = []
        for line in output.strip().split("\n"):
            parts = line.split()
            if len(parts) >= 3:
                partitions.append(
                    {
                        "device": parts[0],
                        "mount_point": parts[1],
                        "filesystem": parts[2],
                    }
                )
        return partitions
