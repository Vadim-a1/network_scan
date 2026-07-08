
import os
import json
import asyncio
import ipaddress
from datetime import datetime
from functools import wraps


import django
from asgiref.sync import sync_to_async
from openpyxl import Workbook

from telegram import Update, ReplyKeyboardMarkup
from telegram.error import TimedOut, NetworkError
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from cameras.models import Camera
from django.utils import timezone


TOKEN = "8906153567:AAGjV-QIWwXoz03ym6qnW6mljKZcbe2PL3c"


keyboard = ReplyKeyboardMarkup(
    [
        ["/ping", "/ping_all"],
        ["/xls", "/help"],
        ["/set_interval 1", "/notify_on"],
        ["/notify_off", "/notify_status"],
        ["/start"],
    ],
    resize_keyboard=True,
)


with open("users.json", "r", encoding="utf-8") as f:
    ALLOWED_USERS = json.load(f)


def is_allowed(update: Update):
    user_id = str(update.effective_user.id)
    return user_id in ALLOWED_USERS


def allowed_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_allowed(update):
            await update.message.reply_text(
                f"⛔ У вас нет доступа к этому боту.\n"
                f"Ваш Telegram ID: {update.effective_user.id}"
            )
            return

        return await func(update, context)

    return wrapper


@sync_to_async
def get_camera_by_ip(ip):
    return Camera.objects.filter(ip=ip).first()


@sync_to_async
def get_all_cameras():
    return list(Camera.objects.all().order_by("id"))


@sync_to_async
def create_camera(ip, name):
    camera, created = Camera.objects.update_or_create(
        ip=ip,
        defaults={
            "name": name,
        },
    )
    return camera, created


@sync_to_async
def save_camera_status(camera, status, ping_value, last_ok=None):
    now = timezone.now()

    camera.status = status
    camera.ping = ping_value
    camera.last_check = now

    update_fields = [
        "status",
        "ping",
        "last_check",
    ]

    if last_ok is not None:
        camera.last_OK = last_ok
        update_fields.append("last_OK")

    camera.save(update_fields=update_fields)


async def ping_ip(ip):
    process = await asyncio.create_subprocess_exec(
        "ping",
        "-c",
        "1",
        "-W",
        "1",
        ip,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )

    await process.wait()

    if process.returncode == 0:
        return ip

    return None


async def check_camera(camera):
    result_ip = await ping_ip(camera.ip)

    if result_ip is not None:
        now = timezone.now()

        await save_camera_status(
            camera,
            "online",
            "OK",
            now
        )

        camera.status = "online"
        camera.ping = "OK"
        camera.last_check = now
        camera.last_OK = now

    else:
        await save_camera_status(
            camera,
            "offline",
            "timeout"
        )

        camera.status = "offline"
        camera.ping = "timeout"
        camera.last_check = timezone.now()

    return camera


async def create_excel_report(cameras):
    wb = Workbook()
    ws = wb.active
    ws.title = "Камеры"

    ws.append(
        [
            "№",
            "Имя",
            "IP",
            "Метка",
            "Тип",
            "Модель",
            "Статус",
            "Ping",
            "Последняя проверка",
            "Последний OK",
        ]
    )

    for index, camera in enumerate(cameras, start=1):
        ws.append(
            [
                index,
                camera.name,
                camera.ip,
                camera.metka,
                camera.type,
                camera.model,
                camera.status,
                camera.ping,
                camera.last_check.strftime("%Y-%m-%d %H:%M:%S")
                if camera.last_check
                else "",
                camera.last_OK.strftime("%Y-%m-%d %H:%M:%S")
                if camera.last_OK
                else "",
            ]
        )

    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 25
    ws.column_dimensions["C"].width = 18
    ws.column_dimensions["D"].width = 20
    ws.column_dimensions["E"].width = 18
    ws.column_dimensions["F"].width = 25
    ws.column_dimensions["G"].width = 15
    ws.column_dimensions["H"].width = 15
    ws.column_dimensions["I"].width = 25
    ws.column_dimensions["J"].width = 25

    filename = f"cameras_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    wb.save(filename)

    return filename


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Добро пожаловать!\n\n"
        "/help - справка по командам\n\n"
        f"🆔 Ваш Telegram ID: {update.effective_user.id}",
        reply_markup=keyboard,
    )


@allowed_only
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 Справка по командам\n\n"
        "/start — показать меню и Telegram ID\n"
        "/help — показать справку\n\n"
        "/ping — проверить одну камеру по IP\n"
        "/ping_all — проверить все камеры из базы Django\n"
        "/xls — проверить камеры и отправить Excel-отчёт\n\n"
        "/add <IP> <Имя> — добавить камеру в базу\n"
        "Пример:\n"
        "/add 192.168.0.20 Камера_1\n\n"
        "/set_interval <минут> — задать интервал рассылки\n"
        "/notify_on — включить рассылку\n"
        "/notify_off — выключить рассылку\n"
        "/notify_status — статус рассылки",
        reply_markup=keyboard,
    )


@allowed_only
async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["waiting_for_ip"] = True
    await update.message.reply_text(
        "Введите IP-адрес камеры:",
        reply_markup=keyboard,
    )


@allowed_only
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("waiting_for_ip"):
        await update.message.reply_text("Сначала введите команду /ping")
        return

    context.user_data["waiting_for_ip"] = False
    ip = update.message.text.strip()

    try:
        ipaddress.ip_address(ip)
    except ValueError:
        await update.message.reply_text("❌ Неверный IP-адрес")
        return

    camera = await get_camera_by_ip(ip)
    result_ip = await ping_ip(ip)

    if camera:
        if result_ip is not None:
            await save_camera_status(
                camera,
                "online",
                "OK",
                timezone.now(),
            )
            status_text = "🟢 online"
            ping_text = "OK"
        else:
            await save_camera_status(
                camera,
                "offline",
                "timeout",
            )
            status_text = "🔴 offline"
            ping_text = "timeout"

        await update.message.reply_text(
            f"📷 {camera.name}\n"
            f"IP: {camera.ip}\n"
            f"Статус: {status_text}\n"
            f"Ping: {ping_text}"
        )
    else:
        if result_ip is not None:
            await update.message.reply_text(
                f"🟢 Неизвестное устройство\n"
                f"IP: {ip}\n"
                f"Статус: online"
            )
        else:
            await update.message.reply_text(
                f"🔴 Неизвестное устройство\n"
                f"IP: {ip}\n"
                f"Статус: offline"
            )


@allowed_only
async def ping_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Проверяю камеры из базы...")

    cameras = await get_all_cameras()

    if not cameras:
        await update.message.reply_text("В базе нет камер.")
        return

    results = await asyncio.gather(
        *[check_camera(camera) for camera in cameras]
    )

    online_count = sum(1 for camera in results if camera.status == "online")
    offline_count = len(results) - online_count

    await update.message.reply_text(
        f"📡 Проверка завершена\n\n"
        f"Всего камер: {len(results)}\n"
        f"🟢 Онлайн: {online_count}\n"
        f"🔴 Офлайн: {offline_count}"
    )


@allowed_only
async def xls_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 Проверяю камеры и создаю Excel...")

    cameras = await get_all_cameras()

    if not cameras:
        await update.message.reply_text("В базе нет камер.")
        return

    checked_cameras = await asyncio.gather(
        *[check_camera(camera) for camera in cameras]
    )

    filename = await create_excel_report(checked_cameras)

    with open(filename, "rb") as file:
        await update.message.reply_document(
            document=file,
            filename=filename,
            caption="📎 Excel-отчёт по камерам",
        )


@allowed_only
async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "Использование:\n/add <IP> <Название>\n\n"
            "Пример:\n/add 192.168.0.20 Камера_1"
        )
        return

    ip = context.args[0]
    name = " ".join(context.args[1:])

    try:
        ipaddress.ip_address(ip)
    except ValueError:
        await update.message.reply_text("❌ Неверный IP-адрес")
        return

    camera, created = await create_camera(ip, name)

    if created:
        await update.message.reply_text(
            f"✅ Камера добавлена\n\n"
            f"Имя: {camera.name}\n"
            f"IP: {camera.ip}"
        )
    else:
        await update.message.reply_text(
            f"♻️ Камера обновлена\n\n"
            f"Имя: {camera.name}\n"
            f"IP: {camera.ip}"
        )


async def periodic_report(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]

    cameras = await get_all_cameras()

    if not cameras:
        await context.bot.send_message(
            chat_id=chat_id,
            text="В базе нет камер.",
        )
        return

    checked_cameras = await asyncio.gather(
        *[check_camera(camera) for camera in cameras]
    )

    online = [camera for camera in checked_cameras if camera.status == "online"]
    count = len(online)
    offline_count = len(checked_cameras) - count

    if count > 7:
        text = (
            f"🟢 Доступных камер: {count}\n\n"
            f"❌Офлайн камер: {offline_count}\n\n"
            f"полный список в Excel-файле."
        )
    else:
        text = f"📡 Доступных камер: {count}\n\n"

        for camera in online:
            text += (
                f"🟢 {camera.name}\n"
                f"IP: {camera.ip}\n\n"
            )

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
    )

    filename = await create_excel_report(checked_cameras)

    with open(filename, "rb") as file:
        await context.bot.send_document(
            chat_id=chat_id,
            document=file,
            filename=filename,
            caption="📎 Excel-файл камер",
        )
    os.remove(filename)


@allowed_only
async def set_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text(
            "Использование:\n/set_interval 5"
        )
        return

    try:
        interval = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Интервал должен быть числом.")
        return

    if interval < 1:
        await update.message.reply_text("Минимальный интервал — 1 минута.")
        return

    context.user_data["notify_interval"] = interval

    await update.message.reply_text(
        f"✅ Интервал установлен: {interval} минут"
    )


@allowed_only
async def notify_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    interval = context.user_data.get("notify_interval")

    if interval is None:
        await update.message.reply_text(
            "Сначала установите интервал:\n/set_interval 5"
        )
        return

    jobs = context.job_queue.get_jobs_by_name(f"notify_{chat_id}")

    for job in jobs:
        job.schedule_removal()

    context.job_queue.run_repeating(
        periodic_report,
        interval=interval * 60,
        first=5,
        name=f"notify_{chat_id}",
        data={"chat_id": chat_id},
    )

    await update.message.reply_text(
        f"✅ Рассылка включена каждые {interval} минут"
    )


@allowed_only
async def notify_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    jobs = context.job_queue.get_jobs_by_name(f"notify_{chat_id}")

    if not jobs:
        await update.message.reply_text("Рассылка уже отключена.")
        return

    for job in jobs:
        job.schedule_removal()

    await update.message.reply_text("🔕 Рассылка отключена.")


@allowed_only
async def notify_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    interval = context.user_data.get("notify_interval")
    jobs = context.job_queue.get_jobs_by_name(f"notify_{chat_id}")

    status = "включена" if jobs else "отключена"

    await update.message.reply_text(
        f"📌 Рассылка: {status}\n"
        f"⏱ Интервал: {interval if interval else 'не установлен'} минут"
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    error = context.error

    if isinstance(error, TimedOut):
        print("Telegram timeout")
    elif isinstance(error, NetworkError):
        print(f"Network error: {error}")
    else:
        print(f"Ошибка: {error}")


app = (
    ApplicationBuilder()
    .token(TOKEN)
    .connect_timeout(60)
    .read_timeout(60)
    .write_timeout(60)
    .pool_timeout(60)
    .build()
)

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("ping", ping_command))
app.add_handler(CommandHandler("ping_all", ping_all))
app.add_handler(CommandHandler("xls", xls_command))
app.add_handler(CommandHandler("add", add))
app.add_handler(CommandHandler("set_interval", set_interval))
app.add_handler(CommandHandler("notify_on", notify_on))
app.add_handler(CommandHandler("notify_off", notify_off))
app.add_handler(CommandHandler("notify_status", notify_status))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

app.add_error_handler(error_handler)

print("Бот запущен")
app.run_polling()