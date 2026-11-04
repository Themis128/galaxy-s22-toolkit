"""Network connectivity information via various system commands."""

from __future__ import annotations

import re
import time
from typing import Any

from .adb import AdbClient
from .models import NetworkInfo


class NetworkModule:
    """Network information module."""

    def __init__(self, client: AdbClient) -> None:
        self.client = client

    def get_network_info(self) -> NetworkInfo:
        """Get comprehensive network information."""
        info = NetworkInfo(
            wifi_connected=False,
            mobile_connected=False,
            internet_reachable=False,
        )

        # Check Wi-Fi
        info.wifi_connected = self._is_wifi_connected()
        if info.wifi_connected:
            info.wifi_ssid = self._get_wifi_ssid()
            info.wifi_ip = self._get_wifi_ip()
            info.wifi_signal_dbm = self._get_wifi_signal()

        # Check mobile data
        info.mobile_connected = self._is_mobile_connected()
        if info.mobile_connected:
            info.mobile_type = self._get_mobile_type()
            info.mobile_ip = self._get_mobile_ip()

        # Get DNS servers
        info.dns_servers = self._get_dns_servers()

        # Get gateway
        info.gateway = self._get_gateway()

        # Test internet connectivity
        info.internet_reachable = self._check_internet()

        return info

    def _is_wifi_connected(self) -> bool:
        """Check if Wi-Fi is connected."""
        try:
            output = self.client.execute("shell", "dumpsys", "wifi")
            # Modern Android (12+/Samsung): check for Supplicant state COMPLETED
            if "Supplicant state: COMPLETED" in output:
                return True
            # Legacy fallback: mNetworkInfo with CONNECTED
            return "mNetworkInfo" in output and "CONNECTED" in output
        except Exception:
            return False

    def _get_wifi_ssid(self) -> str | None:
        """Get current Wi-Fi SSID."""
        try:
            output = self.client.execute("shell", "dumpsys", "wifi")
            # Modern Android (12+/Samsung): SSID embedded in Supplicant state line
            # Format: "Supplicant state: COMPLETED\nmSupplicantStateName=COMPLETED\n..."
            # with SSID in lines like: SSID: "COSMOTE1" or SSID: "\"COSMOTE1\"wpa3-sae"
            match = re.search(
                r'Supplicant state:\s*COMPLETED.*?SSID:\s*"([^"]+)"', output, re.DOTALL
            )
            if match:
                ssid = match.group(1).strip()
                # Clean up embedded security info (e.g., "COSMOTE1\"wpa3-sae" -> "COSMOTE1")
                if '"' in ssid:
                    ssid = ssid.split('"')[0]
                return ssid
            # Legacy parsing: mNetworkInfo block
            match = re.search(r'mNetworkInfo.*?SSID:\s*"([^"]+)"', output, re.DOTALL)
            if match:
                return match.group(1)
            # Alternative parsing
            match = re.search(r'SSID:\s*"([^"]+)"', output)
            if match:
                ssid = match.group(1).strip()
                if '"' in ssid:
                    ssid = ssid.split('"')[0]
                return ssid
        except Exception:
            pass
        return None

    def _get_wifi_ip(self) -> str | None:
        """Get Wi-Fi IP address."""
        try:
            output = self.client.execute("shell", "ip", "addr", "show", "wlan0")
            match = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", output)
            if match:
                return match.group(1)
        except Exception:
            pass
        return None

    def _get_wifi_signal(self) -> int | None:
        """Get Wi-Fi signal strength in dBm."""
        try:
            output = self.client.execute("shell", "dumpsys", "wifi")
            # Modern Android (12+/Samsung): RSSI in Supplicant state block
            match = re.search(r"Supplicant state:\s*COMPLETED.*?RSSI:\s*(-?\d+)", output, re.DOTALL)
            if match:
                return int(match.group(1))
            # Legacy RSSI format
            match = re.search(r"RSSI:\s*(-?\d+)", output)
            if match:
                return int(match.group(1))
            # Alternative
            match = re.search(r"signalStrength.*?(-?\d+)", output)
            if match:
                return int(match.group(1))
        except Exception:
            pass
        return None

    def _is_mobile_connected(self) -> bool:
        """Check if mobile data is connected."""
        try:
            output = self.client.execute("shell", "dumpsys", "telephony.registry")
            return "mDataConnectionState=2" in output  # 2 = CONNECTED
        except Exception:
            return False

    def _get_mobile_type(self) -> str | None:
        """Get mobile network type (LTE, 5G, etc.)."""
        try:
            output = self.client.execute("shell", "getprop", "gsm.network.type")
            return output.strip() or None
        except Exception:
            return None

    def _get_mobile_ip(self) -> str | None:
        """Get mobile data IP address."""
        try:
            output = self.client.execute("shell", "ip", "addr", "show", "rmnet0")
            match = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", output)
            if match:
                return match.group(1)
            # Try other common mobile interfaces
            for iface in ["rmnet1", "rmnet_data0", "ccmni0"]:
                try:
                    output = self.client.execute("shell", "ip", "addr", "show", iface)
                    match = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", output)
                    if match:
                        return match.group(1)
                except Exception:
                    continue
        except Exception:
            pass
        return None

    def _get_dns_servers(self) -> list[str]:
        """Get DNS servers from system properties."""
        try:
            dns1 = self.client.execute("shell", "getprop", "net.dns1")
            dns2 = self.client.execute("shell", "getprop", "net.dns2")
            dns3 = self.client.execute("shell", "getprop", "net.dns3")
            dns4 = self.client.execute("shell", "getprop", "net.dns4")

            servers = []
            for dns in [dns1, dns2, dns3, dns4]:
                dns = dns.strip()
                if dns and dns != "0.0.0.0":
                    servers.append(dns)
            return servers
        except Exception:
            return []

    def _get_gateway(self) -> str | None:
        """Get default gateway."""
        # The default route often lives in a per-network table on modern
        # Android, so `ip route show default` alone can come back empty.
        for args in (
            ("shell", "ip", "route", "show", "default"),
            ("shell", "ip", "route", "show", "table", "all"),
        ):
            try:
                output = self.client.execute(*args)
                match = re.search(r"default via (\d+\.\d+\.\d+\.\d+)", output)
                if match:
                    return match.group(1)
            except Exception:
                continue
        return None

    def _check_internet(self, host: str = "8.8.8.8", port: int = 53, timeout: float = 3.0) -> bool:
        """Check internet connectivity via TCP connection."""
        try:
            # Try to connect via ADB shell
            result = self.client.execute(
                "shell",
                "timeout",
                str(int(timeout)),
                "nc",
                "-z",
                "-w",
                str(int(timeout)),
                host,
                str(port),
                "&&",
                "echo",
                "connected",  # toybox nc is silent on success; print a marker
                check=False,
            )
            return "succeeded" in result.lower() or "connected" in result.lower()
        except Exception:
            pass

        # Fallback: try ping
        try:
            result = self.client.execute(
                "shell",
                "ping",
                "-c",
                "1",
                # toybox ping -W is in SECONDS (ms here fails instantly)
                "-W",
                str(max(1, int(timeout))),
                host,
                check=False,
            )
            return "1 received" in result
        except Exception:
            return False

    def check_internet_connectivity(self) -> bool:
        """Check internet connectivity (public method)."""
        return self._check_internet()

    def check_connectivity(self) -> dict[str, bool]:
        """Check connectivity (internet and DNS) for diagnostics compatibility."""
        internet = self._check_internet()
        dns = self.test_dns_resolution()
        return {"internet": internet, "dns": dns}

    def check_dns(self) -> bool:
        """Check DNS resolution for diagnostics compatibility."""
        return self.test_dns_resolution()

    def get_wifi_info(self) -> dict[str, Any]:
        """Get Wi-Fi info for diagnostics compatibility."""
        ssid = self._get_wifi_ssid()
        rssi = self._get_wifi_signal()
        # Get link speed
        link_speed = None
        try:
            output = self.client.execute("shell", "dumpsys", "wifi")
            match = re.search(r"LinkSpeed:\s*(\d+)", output)
            if match:
                link_speed = int(match.group(1))
        except Exception:
            pass

        return {
            "ssid": ssid or "Unknown",
            "rssi": rssi or 0,
            "link_speed": link_speed or 0,
        }

    def test_dns_resolution(self, domain: str = "google.com", timeout: float = 3.0) -> bool:
        """Test DNS resolution; timeout (seconds) bounds the probe."""
        try:
            output = self.client.execute("shell", "nslookup", domain, check=False)
            if "Name:" in output or "Address:" in output:
                return True
            # nslookup is absent on recent Android (toybox dropped it);
            # ping only runs when the hostname resolved
            output = self.client.execute(
                "shell", "ping", "-c", "1", "-W", str(max(1, int(timeout))), domain, check=False
            )
            return "1 received" in output or "1 packets received" in output
        except Exception:
            return False

    def get_wifi_scan(self) -> list[dict[str, Any]]:
        """Get Wi-Fi scan results."""
        try:
            output = self.client.execute(
                "shell", "dumpsys", "wifi", "|", "grep", "-A", "20", "ScanResult"
            )
            networks = []
            for line in output.split("\n"):
                line = line.strip()
                if line.startswith("ScanResult"):
                    # Parse ScanResult line with space-separated key:value pairs
                    # Format: ScanResult[0]: BSSID: aa:bb:cc:dd:ee:ff SSID: "MyWiFiNetwork" freq: 2437 level: -45 ...
                    parts = line.split(":", 1)
                    if len(parts) < 2:
                        continue
                    # The rest of the line has space-separated key:value pairs
                    scan_data = parts[1].strip()
                    network = {}
                    # Parse key:value pairs - handle quoted values
                    # Use regex to find all key: value pairs
                    # Pattern matches: key: "value" or key: value (non-greedy until space+key: or end)
                    pairs = re.findall(r'(\w+):\s*(?:"([^"]*)"|(\S+))', scan_data)
                    for key, quoted_val, unquoted_val in pairs:
                        value = quoted_val if quoted_val else unquoted_val
                        network[key.lower()] = value
                    # Map common keys to expected names
                    if "ssid" in network:
                        network["ssid"] = network["ssid"].strip('"')
                    if "level" in network:
                        try:
                            network["signal_dbm"] = int(network["level"])
                        except ValueError:
                            pass
                    if "bssid" in network:
                        network["bssid"] = network["bssid"]
                    if "freq" in network:
                        try:
                            network["freq"] = int(network["freq"])
                        except ValueError:
                            pass
                    if network:
                        networks.append(network)
            return networks
        except Exception:
            return []

    def get_http_response_time(
        self, url: str = "http://www.google.com", timeout: int = 5
    ) -> float | None:
        """Measure HTTP response time."""
        try:
            start = time.time()
            result = self.client.execute(
                "shell",
                "curl",
                "-s",
                "-o",
                "/dev/null",
                "-w",
                "%{http_code}",
                "--max-time",
                str(timeout),
                url,
                check=False,
            )
            elapsed = time.time() - start
            if result.strip().isdigit() and int(result) == 200:
                return elapsed
        except Exception:
            pass
        return None

    def get_network_stats(self) -> dict[str, dict[str, int]]:
        """Get network interface statistics for all interfaces."""
        try:
            output = self.client.execute("shell", "cat", "/proc/net/dev")
            stats = {}
            for line in output.split("\n"):
                line = line.strip()
                if (
                    not line
                    or line.startswith("Inter-|")
                    or line.startswith("face")
                    or line.startswith("Iface")
                ):
                    continue
                parts = line.split()
                if len(parts) >= 10:
                    iface = parts[0].rstrip(":")
                    if iface:
                        stats[iface] = {
                            "rx_bytes": int(parts[1]),
                            "tx_bytes": int(parts[9]),
                        }
            return stats
        except Exception:
            return {}
