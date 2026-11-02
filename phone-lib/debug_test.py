"""Debug test for network stats."""

from phone.network import NetworkModule
from unittest.mock import MagicMock

# Mock data from conftest
MOCK_PROC_NET_DEV = """Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
  wlan0: 1000000   5000    0    0    0     0          0         0  2000000   6000    0    0    0     0       0          0
"""

responses = {
    ("shell", "cat", "/proc/net/dev"): MOCK_PROC_NET_DEV,
}

client = MagicMock()
client.serial = "RFCTA0AEKZP"

def mock_execute(*args, **kwargs):
    rv = client.execute.return_value
    if isinstance(rv, str) and rv != "":
        return rv
    key = tuple(args)
    if key in responses:
        return responses[key]
    return ""

client.execute = MagicMock(side_effect=mock_execute)
client.execute.return_value = ""

# Now test
module = NetworkModule(client)
stats = module.get_network_stats()
print("Stats:", stats)
print("wlan0 in stats:", "wlan0" in stats)
if "wlan0" in stats:
    print("rx_bytes:", stats["wlan0"]["rx_bytes"])
    print("tx_bytes:", stats["wlan0"]["tx_bytes"])