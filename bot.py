import inspect
import ipaddress
import re
import socket
import subprocess

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from config import NETWORK, TOKEN

try:
    from scapy.all import ARP, Ether, conf, srp
except ImportError:
    ARP = None
    Ether = None
    conf = None
    srp = None

try:
    from mac_vendor_lookup import AsyncMacLookup, MacLookup
except ImportError:
    AsyncMacLookup = None
    MacLookup = None


vendor_lookup = None
vendor_lookup_ready = False
vendor_cache = {}
last_scan_info = ""


def normalize_mac(mac: str) -> str:
    return mac.strip().upper().replace("-", ":")


def get_oui(mac: str) -> str:
    return normalize_mac(mac)[:8]


def is_private_mac(mac: str) -> bool:
    first_octet = int(normalize_mac(mac).split(":")[0], 16)
    return bool(first_octet & 0b00000010)


async def maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


async def init_vendor_lookup() -> None:
    global vendor_lookup, vendor_lookup_ready

    if vendor_lookup_ready:
        return

    if AsyncMacLookup:
        vendor_lookup = AsyncMacLookup()
    elif MacLookup:
        vendor_lookup = MacLookup()
    else:
        print("mac-vendor-lookup is not installed. Will use Scapy vendor database only.")
        vendor_lookup_ready = True
        return

    try:
        await maybe_await(vendor_lookup.update_vendors())
        print("mac-vendor-lookup database updated.")
    except Exception as error:
        print(f"Could not update mac-vendor-lookup database: {error}")
        print("Will use local databases only.")

    vendor_lookup_ready = True


def get_vendor_from_scapy(mac: str) -> str | None:
    if not conf or not getattr(conf, "manufdb", None):
        return None

    mac = normalize_mac(mac)
    manufdb = conf.manufdb

    for method_name in ("_get_manuf", "_get_short_manuf"):
        method = getattr(manufdb, method_name, None)
        if not method:
            continue

        try:
            vendor = method(mac)
        except Exception:
            continue

        if vendor and vendor != mac:
            return str(vendor)

    return None


async def get_vendor_from_mac_lookup(mac: str) -> str | None:
    await init_vendor_lookup()

    if not vendor_lookup:
        return None

    try:
        vendor = await maybe_await(vendor_lookup.lookup(normalize_mac(mac)))
    except Exception:
        return None

    if vendor:
        return str(vendor)

    return None


async def get_vendor(mac: str) -> str:
    mac = normalize_mac(mac)

    if mac in vendor_cache:
        return vendor_cache[mac]

    if is_private_mac(mac):
        vendor_cache[mac] = "Неизвестно (случайный/private MAC)"
        return vendor_cache[mac]

    vendor = get_vendor_from_scapy(mac)
    if not vendor:
        vendor = await get_vendor_from_mac_lookup(mac)

    if not vendor:
        vendor = f"Неизвестно (OUI {get_oui(mac)} не найден в базе)"

    vendor_cache[mac] = vendor
    return vendor


def get_scan_interface() -> str | None:
    if not conf or not NETWORK:
        return None

    try:
        network = ipaddress.ip_network(NETWORK, strict=False)
        probe_ip = str(next(network.hosts()))
        route = conf.route.route(probe_ip)
        return route[0] if route else None
    except Exception:
        return None


def get_hostname(ip: str) -> str:
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return "-"


def scan_with_scapy():
    global last_scan_info

    if not ARP or not Ether or not srp:
        raise RuntimeError("Не установлена библиотека scapy. Установи: pip install scapy")

    iface = get_scan_interface()
    packet = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=NETWORK)

    kwargs = {
        "timeout": 3,
        "retry": 1,
        "verbose": False,
    }
    if iface:
        kwargs["iface"] = iface

    answered = srp(packet, **kwargs)[0]
    last_scan_info = f"NETWORK={NETWORK}, iface={iface or 'auto'}, replies={len(answered)}"

    devices = []
    for _, received in answered:
        ip = received.psrc
        mac = normalize_mac(received.hwsrc)
        devices.append({
            "ip": ip,
            "mac": mac,
            "hostname": get_hostname(ip),
            "source": "scapy",
        })

    return devices


def scan_with_arp_cache():
    if not NETWORK:
        return []

    network = ipaddress.ip_network(NETWORK, strict=False)

    try:
        result = subprocess.run(
            ["arp", "-a"],
            capture_output=True,
            text=True,
            encoding="cp866",
            errors="ignore",
            timeout=5,
        )
    except Exception:
        return []

    devices = []
    pattern = re.compile(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F-]{17})\s+")

    for line in result.stdout.splitlines():
        match = pattern.search(line)
        if not match:
            continue

        ip = match.group(1)
        mac = normalize_mac(match.group(2))

        try:
            if ipaddress.ip_address(ip) not in network:
                continue
        except ValueError:
            continue

        if mac == "FF:FF:FF:FF:FF:FF":
            continue

        devices.append({
            "ip": ip,
            "mac": mac,
            "hostname": get_hostname(ip),
            "source": "arp-cache",
        })

    return devices


def unique_devices(devices):
    by_ip = {}
    for device in devices:
        by_ip[device["ip"]] = device

    return sorted(
        by_ip.values(),
        key=lambda device: tuple(map(int, device["ip"].split("."))),
    )


def scan_network():
    """Возвращает список устройств в локальной сети."""
    if not NETWORK:
        raise RuntimeError("Локальная сеть не определена. Проверь get_network.py")

    devices = scan_with_scapy()

    if not devices:
        devices = scan_with_arp_cache()

    return unique_devices(devices)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Network Monitor\n\n"
        "/online - показать устройства в сети"
    )


async def online(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Сканирую сеть...")

    try:
        devices = scan_network()
        for device in devices:
            device["vendor"] = await get_vendor(device["mac"])
    except Exception as error:
        await update.message.reply_text(f"Ошибка сканирования: {error}")
        return

    if not devices:
        await update.message.reply_text(
            "Устройства не найдены.\n"
            f"Параметры скана: {last_scan_info or 'нет данных'}\n"
            "Попробуй запустить PowerShell от имени администратора."
        )
        return

    lines = [f"Онлайн устройств: {len(devices)}", f"Скан: {last_scan_info}", ""]

    for device in devices:
        lines.extend([
            f"Устройство: {device['hostname']}",
            f"IP: {device['ip']}",
            f"MAC: {device['mac']}",
            f"Vendor: {device['vendor']}",
            
            "",
        ])

    message = "\n".join(lines)

    for start_index in range(0, len(message), 4000):
        await update.message.reply_text(message[start_index:start_index + 4000])


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(f"Bot error: {context.error}")


def main() -> None:
    if not TOKEN or ":" not in TOKEN:
        raise RuntimeError("Укажи настоящий токен Telegram-бота в config.py")

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("online", online))
    app.add_error_handler(error_handler)

    print("Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()

