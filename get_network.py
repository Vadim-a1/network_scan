import socket
import psutil
import ipaddress


def get_local_network():
    for interface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                network = ipaddress.IPv4Network(
                    f"{addr.address}/{addr.netmask}",
                    strict=False
                )
                return str(network)

    return None