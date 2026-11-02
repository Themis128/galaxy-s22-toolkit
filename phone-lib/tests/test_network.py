"""Unit tests for network module."""

from __future__ import annotations

from phone.network import NetworkModule


class TestNetworkModule:
    """Tests for NetworkModule."""

    def test_get_network_info_wifi(self, mock_adb_client):
        """Test getting network info when WiFi is connected."""
        module = NetworkModule(mock_adb_client)
        network = module.get_network_info()

        assert network.wifi_connected is True
        assert network.wifi_ssid == "MyWiFiNetwork"
        assert network.wifi_ip == "192.168.1.100"
        assert network.wifi_signal_dbm == -45
        assert network.dns_servers == ["192.168.1.1", "8.8.8.8"]
        assert network.gateway == "192.168.1.1"
        assert network.internet_reachable is True

    def test_check_internet_connectivity(self, mock_adb_client):
        """Test internet connectivity check."""
        module = NetworkModule(mock_adb_client)
        reachable = module.check_internet_connectivity()
        assert reachable is True

    def test_test_dns_resolution(self, mock_adb_client):
        """Test DNS resolution."""
        module = NetworkModule(mock_adb_client)

        # Should work with default DNS
        result = module.test_dns_resolution("google.com")
        assert result is True

        # Should fail for invalid domain
        result = module.test_dns_resolution("invalid.domain.that.does.not.exist.12345")
        assert result is False

    def test_get_wifi_scan(self, mock_adb_client):
        """Test WiFi scan results."""
        mock_adb_client.execute.return_value = """ScanResult[0]: BSSID: aa:bb:cc:dd:ee:ff SSID: "MyWiFiNetwork" freq: 2437 level: -45 timestamp: 123456789 distanceCm: -1 distanceSdCm: -1 venAnpi: 0 venMcs: 0 venNss: 0 venRxStreams: 0 venTxStreams: 0
ScanResult[1]: BSSID: 11:22:33:44:55:66 SSID: "OtherNetwork" freq: 5180 level: -65 timestamp: 123456790 distanceCm: -1 distanceSdCm: -1 venAnpi: 0 venMcs: 0 venNss: 0 venRxStreams: 0 venTxStreams: 0
"""
        module = NetworkModule(mock_adb_client)
        networks = module.get_wifi_scan()

        assert len(networks) == 2
        assert networks[0]["ssid"] == "MyWiFiNetwork"
        assert networks[0]["signal_dbm"] == -45
        assert networks[1]["ssid"] == "OtherNetwork"
        assert networks[1]["signal_dbm"] == -65

    def test_get_http_response_time(self, mock_adb_client):
        """Test HTTP response time measurement."""
        module = NetworkModule(mock_adb_client)
        response_time = module.get_http_response_time("http://www.google.com")

        assert isinstance(response_time, float)
        assert response_time >= 0

    def test_get_network_stats(self, mock_adb_client):
        """Test getting network statistics using fixture's default mock data."""
        module = NetworkModule(mock_adb_client)
        stats = module.get_network_stats()

        assert "wlan0" in stats
        # Fixture has: wlan0 rx=1000000, tx=2000000
        assert stats["wlan0"]["rx_bytes"] == 1000000
        assert stats["wlan0"]["tx_bytes"] == 2000000
