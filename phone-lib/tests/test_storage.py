"""Unit tests for storage module."""

from __future__ import annotations

from phone.storage import StorageModule


class TestStorageModule:
    """Tests for StorageModule."""

    def test_get_storage_info(self, mock_adb_client, mock_storage_info):
        """Test parsing storage info from df output."""
        module = StorageModule(mock_adb_client)
        storages = module.get_storage_info()

        assert len(storages) == 4  # /, /data, /cache, /sdcard

        # Check /data partition
        data_storage = next((s for s in storages if s.mount_point == "/data"), None)
        assert data_storage is not None
        assert data_storage.filesystem == "f2fs"
        # Usage: 3500000/5242880 = 66.7% (approx 67%)
        assert abs(data_storage.usage_percent - 67.0) < 2.0

    def test_get_data_storage(self, mock_adb_client):
        """Get /data partition specifically."""
        module = StorageModule(mock_adb_client)
        data = module.get_data_storage()

        assert data is not None
        assert data.mount_point == "/data"
        assert data.filesystem == "f2fs"

    def test_get_internal_storage(self, mock_adb_client):
        """Get internal storage (/sdcard)."""
        module = StorageModule(mock_adb_client)
        internal = module.get_internal_storage()

        assert internal is not None
        assert internal.mount_point == "/sdcard"
        assert internal.filesystem == "vfat"

    def test_get_total_space(self, mock_adb_client):
        """Get total space across all partitions."""
        module = StorageModule(mock_adb_client)
        total = module.get_total_space()

        # Sum of all partition totals in bytes
        expected = (2097152 + 5242880 + 1048576 + 52428800) * 1024
        assert total == expected

    def test_get_used_space(self, mock_adb_client):
        """Get used space across all partitions."""
        module = StorageModule(mock_adb_client)
        used = module.get_used_space()

        expected = (1200000 + 3500000 + 800000 + 40000000) * 1024
        assert used == expected

    def test_get_free_space(self, mock_adb_client):
        """Get free space across all partitions."""
        module = StorageModule(mock_adb_client)
        free = module.get_free_space()

        expected = (897152 + 1742880 + 248576 + 12428800) * 1024
        assert free == expected

    def test_filesystem_guessing(self, mock_adb_client):
        """Test filesystem type guessing from mount points."""
        module = StorageModule(mock_adb_client)

        assert module._guess_filesystem("/") == "ext4"
        assert module._guess_filesystem("/system") == "ext4"
        assert module._guess_filesystem("/vendor") == "ext4"
        assert module._guess_filesystem("/product") == "ext4"
        assert module._guess_filesystem("/data") == "f2fs"
        assert module._guess_filesystem("/data/media") == "f2fs"
        assert module._guess_filesystem("/sdcard") == "vfat"
        assert module._guess_filesystem("/storage/emulated/0") == "vfat"
        assert module._guess_filesystem("/unknown") == "unknown"

    def test_find_large_files(self, mock_adb_client):
        """Test finding large files."""
        mock_adb_client.execute.return_value = """-rw-r--r-- 1 root root 209715200 Jan 1 00:00 /data/large_file.dat
-rw-r--r-- 1 root root 104857600 Jan 1 00:00 /data/another_large.log
-rw-r--r-- 1 root root 52428800 Jan 1 00:00 /data/small_file.tmp
"""
        module = StorageModule(mock_adb_client)
        files = module.find_large_files("/data", min_size_mb=50, limit=10)

        assert len(files) == 3
        assert files[0]["path"] == "/data/large_file.dat"
        assert files[0]["size_mb"] == 200.0
        assert files[1]["path"] == "/data/another_large.log"
        assert files[2]["path"] == "/data/small_file.tmp"

    def test_get_mounted_partitions(self, mock_adb_client):
        """Test parsing /proc/mounts."""
        module = StorageModule(mock_adb_client)
        partitions = module.get_mounted_partitions()

        assert len(partitions) >= 2
        # Check /data partition
        data_part = next((p for p in partitions if p["mount_point"] == "/data"), None)
        assert data_part is not None
        assert data_part["filesystem"] == "f2fs"

        # Check /sdcard partition
        sdcard_part = next((p for p in partitions if p["mount_point"] == "/sdcard"), None)
        assert sdcard_part is not None
        assert sdcard_part["filesystem"] == "vfat"
