import socket
import ipaddress
import subprocess
import platform

from scapy.all import ARP, Ether, srp
from mac_vendor_lookup import MacLookup


# -------------------------
# Vendor database
# -------------------------
lookup = MacLookup()
try:
    lookup.update_vendors()
except:
    pass


# -------------------------
# Get local network (/24 fallback)
# -------------------------
def get_network():
    hostname = socket.gethostname()

    try:
        local_ip = socket.gethostbyname(hostname)
    except:
        raise RuntimeError("Не удалось получить локальный IP")

    if local_ip.startswith("127."):
        raise RuntimeError("Локальный IP = 127.x.x.x")

    return str(ipaddress.IPv4Network(f"{local_ip}/24", strict=False))


# -------------------------
# Vendor
# -------------------------
def get_vendor(mac: str) -> str:
    try:
        return lookup.lookup(mac.upper())
    except:
        return "Unknown"


# -------------------------
# Hostname resolution (multi-layer)
# -------------------------
def get_hostname(ip: str) -> str:
    # 1. DNS reverse
    try:
        name = socket.gethostbyaddr(ip)[0]
        if name and name != ip:
            return name
    except:
        pass

    # 2. NetBIOS (Windows only)
    if platform.system() == "Windows":
        try:
            out = subprocess.check_output(
                ["nbtstat", "-A", ip],
                text=True,
                stderr=subprocess.DEVNULL
            )

            for line in out.splitlines():
                if "<00>" in line:
                    parts = line.split()
                    if parts:
                        return parts[0]
        except:
            pass

    # 3. mDNS fallback (very weak, but safe)
    try:
        name = socket.getfqdn(ip)
        if name and name != ip:
            return name
    except:
        pass

    return "-"


# -------------------------
# Scan network
# -------------------------
def scan_network():
    network = get_network()

    packet = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=network)
    answered = srp(packet, timeout=2, verbose=False)[0]

    devices = []

    for _, r in answered:
        ip = r.psrc
        mac = r.hwsrc

        devices.append({
            "ip": ip,
            "mac": mac,
            "vendor": get_vendor(mac),
            "hostname": get_hostname(ip),
        })

    return sorted(
        devices,
        key=lambda x: tuple(map(int, x["ip"].split(".")))
    )