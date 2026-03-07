import io
import logging
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import qrcode

from config import get_settings
from database import (
    create_device,
    list_devices,
    get_device_by_token,
    get_device_by_id,
    set_device_name,
    set_device_packages,
    delete_device,
    get_channel_id,
    set_channel_id,
    get_alert_chat_id,
    set_alert_chat_id,
    get_devices_overdue_for_offline_alert,
    mark_device_offline_alert_sent,
    search_notifications,
    ONLINE_THRESHOLD_MINUTES,
)

logger = logging.getLogger("bot")

# Callback data
CB_MAIN = "m_main"
CB_DEVICES = "m_devices"
CB_CHANNEL = "m_channel"
CB_SETTINGS = "m_settings"
CB_NEW = "m_new"
CB_DEVICE = "d_"  # d_1, d_2, ...
CB_DEVICE_NAME = "dn_"  # dn_1
CB_DEVICE_PKG = "dp_"  # dp_1
CB_DEVICE_DEL = "dd_"  # dd_1
CB_DEVICE_DEL_CONFIRM = "dc_"  # dc_1
CB_BACK_DEVICES = "m_devices"
CB_SETNAME_PROMPT = "snp_"  # snp_1 — запрос имени для устройства id=1
CB_ALERT_HERE = "m_alert_here"
CB_DEVICE_CHECK = "dch_"  # dch_1 — проверить устройство (обновить статус)
CB_HISTORY = "m_history"
CB_SEARCH = "m_search"

# Формат QR для приложения: EVATEAM\n<url>\n<token>
QR_PREFIX = "EVATEAM"


def _e(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _parse_last_seen(iso_str: str | None) -> datetime | None:
    if not iso_str or not iso_str.strip():
        return None
    try:
        return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _is_online(last_seen: datetime | None) -> bool:
    if not last_seen:
        return False
    return (datetime.now(timezone.utc) - last_seen).total_seconds() < ONLINE_THRESHOLD_MINUTES * 60


def _make_qr_bytes(payload: str) -> io.BytesIO:
    buf = io.BytesIO()
    qr = qrcode.QRCode(version=1, box_size=4, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    # PyPNG backend не принимает format=; PIL принимает
    try:
        img.save(buf, format="PNG")
    except (TypeError, AttributeError):
        img.save(buf)
    buf.seek(0)
    return buf


def _format_status(device: dict) -> tuple[str, str]:
    """Возвращает (emoji_status, status_text) для устройства."""
    ls = _parse_last_seen(device.get("last_seen"))
    online = _is_online(ls)
    if online:
        if ls:
            sec = (datetime.now(timezone.utc) - ls).total_seconds()
            if sec < 60:
                return "🟢", "только что"
            if sec < 3600:
                return "🟢", f"{int(sec // 60)} мин назад"
            return "🟢", f"{int(sec // 3600)} ч назад"
        return "🟢", "в сети"
    if ls:
        delta = datetime.now(timezone.utc) - ls
        mins = int(delta.total_seconds() / 60)
        if mins < 60:
            return "🔴", f"офлайн {mins} мин"
        hours = mins // 60
        if hours < 24:
            return "🔴", f"офлайн {hours} ч"
        return "🔴", f"офлайн {hours // 24} д"
    return "🔴", "никогда не подключалось"


def _main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📱 Устройства", callback_data=CB_DEVICES),
            InlineKeyboardButton("⚙️ Настройки", callback_data=CB_SETTINGS),
        ],
        [
            InlineKeyboardButton("📢 Канал", callback_data=CB_CHANNEL),
        ],
        [
            InlineKeyboardButton("📜 История и поиск", callback_data=CB_HISTORY),
        ],
        [
            InlineKeyboardButton("➕ Новое устройство", callback_data=CB_NEW),
        ],
    ])


def _devices_list_keyboard() -> InlineKeyboardMarkup:
    devices = list_devices()
    buttons = []
    for d in devices:
        name = (d.get("name") or "Устройство")[:20]
        emoji, _ = _format_status(d)
        buttons.append([InlineKeyboardButton(f"{emoji} {_e(name)}", callback_data=f"{CB_DEVICE}{d['id']}")])
    buttons.append([InlineKeyboardButton("◀️ В меню", callback_data=CB_MAIN)])
    return InlineKeyboardMarkup(buttons)


def _device_detail_keyboard(device_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ Имя", callback_data=f"{CB_DEVICE_NAME}{device_id}"),
            InlineKeyboardButton("📦 Приложения", callback_data=f"{CB_DEVICE_PKG}{device_id}"),
        ],
        [InlineKeyboardButton("🔄 Проверить устройство", callback_data=f"{CB_DEVICE_CHECK}{device_id}")],
        [InlineKeyboardButton("🗑 Удалить", callback_data=f"{CB_DEVICE_DEL}{device_id}")],
        [InlineKeyboardButton("◀️ К списку устройств", callback_data=CB_BACK_DEVICES)],
    ])


def _device_delete_confirm_keyboard(device_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Да, удалить", callback_data=f"{CB_DEVICE_DEL_CONFIRM}{device_id}"),
            InlineKeyboardButton("❌ Отмена", callback_data=f"{CB_DEVICE}{device_id}"),
        ],
    ])


def _channel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ В меню", callback_data=CB_MAIN)],
    ])


def _settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Канал для уведомлений", callback_data=CB_CHANNEL)],
        [InlineKeyboardButton("📬 Алерты об офлайне устройств — сюда в бота", callback_data=CB_ALERT_HERE)],
        [InlineKeyboardButton("◀️ В меню", callback_data=CB_MAIN)],
    ])


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user:
        return
    text = (
        "👋 <b>Уведомления в Telegram</b>\n\n"
        "Пересылка SMS и уведомлений с телефона в канал.\n"
        "Управляйте устройствами и настройками кнопками ниже."
    )
    if update.message:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=_main_menu_keyboard())
    else:
        await update.callback_query.message.reply_text(text, parse_mode="HTML", reply_markup=_main_menu_keyboard())


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()
    data = query.data

    if data == CB_MAIN:
        text = "📋 <b>Главное меню</b>\n\nВыберите раздел:"
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=_main_menu_keyboard())
        return

    if data == CB_DEVICES:
        devices = list_devices()
        if not devices:
            text = "📱 <b>Устройства</b>\n\nНет устройств.\nНажмите «➕ Новое устройство» в главном меню."
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В меню", callback_data=CB_MAIN)]])
        else:
            online_count = sum(1 for d in devices if _is_online(_parse_last_seen(d.get("last_seen"))))
            text = (
                f"📱 <b>Устройства</b>\n\n"
                f"Всего: {len(devices)}  ·  В сети: {online_count} 🟢  ·  Не в сети: {len(devices) - online_count} 🔴\n\n"
                "Выберите устройство:"
            )
            kb = _devices_list_keyboard()
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=kb)
        return

    if data == CB_CHANNEL:
        ch = get_channel_id()
        if ch:
            text = f"📢 <b>Канал для уведомлений</b>\n\nТекущий: <code>{_e(ch)}</code>\n\nЧтобы изменить — отправьте:\n<code>/channel -1001234567890</code>"
        else:
            text = "📢 <b>Канал для уведомлений</b>\n\nКанал не задан.\nОтправьте: <code>/channel -1001234567890</code>"
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=_channel_keyboard())
        return

    if data == CB_SETTINGS:
        alert_chat = get_alert_chat_id()
        alert_status = "✅ Настроено: алерты об офлайне приходят сюда в бота." if alert_chat else "Алерты об упавших устройствах не идут в канал — только в бота. Нажмите кнопку ниже."
        text = f"⚙️ <b>Настройки</b>\n\n{alert_status}\n\nВыберите параметр:"
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=_settings_keyboard())
        return

    if data == CB_ALERT_HERE:
        chat_id = query.message.chat.id if query.message else None
        if chat_id is not None:
            set_alert_chat_id(str(chat_id))
            await query.edit_message_text(
                "✅ Готово. Уведомления об упавших устройствах будут приходить сюда в бота (в канал не отправляются).",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В меню", callback_data=CB_MAIN)]]),
            )
        else:
            await query.answer("Ошибка", show_alert=True)
        return

    if data == CB_NEW:
        name = "Устройство"
        token = create_device(name)
        device = get_device_by_token(token)
        if not device:
            await query.answer("Ошибка создания устройства", show_alert=True)
            return
        api_url = (get_settings().api_base_url or "https://ваш-сервер.com").rstrip("/")
        device_id = device["id"]
        # QR для приложения: EVATEAM\n<url>\n<token>
        qr_payload = f"{QR_PREFIX}\n{api_url}\n{token}"
        qr_bytes = _make_qr_bytes(qr_payload)
        await query.message.reply_photo(
            photo=qr_bytes,
            caption="📱 Отсканируйте QR в приложении EVATEAM (кнопка «Сканировать QR») для добавления устройства.",
        )
        text = (
            "✅ <b>Устройство добавлено</b>\n\n"
            f"<b>Токен</b>: <code>{_e(token)}</code>\n\n"
            f"<b>URL сервера</b>: <code>{_e(api_url)}</code>\n\n"
            "Задайте имя устройству кнопкой ниже. В приложении добавьте «Сообщения» для SMS."
        )
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Задать имя устройству", callback_data=f"{CB_SETNAME_PROMPT}{device_id}")],
                [InlineKeyboardButton("📱 К списку устройств", callback_data=CB_DEVICES)],
                [InlineKeyboardButton("◀️ В меню", callback_data=CB_MAIN)],
            ]),
        )
        return

    if data.startswith(CB_SETNAME_PROMPT):
        try:
            did = int(data[len(CB_SETNAME_PROMPT):])
        except ValueError:
            return
        dev = get_device_by_id(did)
        if not dev:
            await query.edit_message_text("Устройство не найдено.")
            return
        context.user_data["pending_device_name"] = did
        await query.edit_message_text(
            "✏️ Отправьте <b>одним сообщением</b> имя для этого устройства (например: <i>Телефон мамы</i>).",
            parse_mode="HTML",
        )
        return

    if data.startswith(CB_DEVICE_DEL_CONFIRM):
        try:
            did = int(data[len(CB_DEVICE_DEL_CONFIRM):])
        except ValueError:
            return
        devices = list_devices()
        dev = next((d for d in devices if d["id"] == did), None)
        if not dev:
            await query.edit_message_text("Устройство не найдено.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В меню", callback_data=CB_MAIN)]]))
            return
        delete_device(dev["device_token"])
        await query.edit_message_text(
            f"🗑 Устройство «{_e(dev.get('name') or 'Устройство')}» удалено.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ К устройствам", callback_data=CB_DEVICES)]]),
        )
        return

    if data.startswith(CB_DEVICE_DEL):
        try:
            did = int(data[len(CB_DEVICE_DEL):])
        except ValueError:
            return
        devices = list_devices()
        dev = next((d for d in devices if d["id"] == did), None)
        if not dev:
            await query.edit_message_text("Устройство не найдено.")
            return
        text = f"Удалить устройство «{_e(dev.get('name') or 'Устройство')}»?"
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=_device_delete_confirm_keyboard(did))
        return

    if data.startswith(CB_DEVICE_NAME) or data.startswith(CB_DEVICE_PKG):
        try:
            did = int(data[3:])  # dn_1 or dp_1
        except ValueError:
            return
        devices = list_devices()
        dev = next((d for d in devices if d["id"] == did), None)
        if not dev:
            await query.edit_message_text("Устройство не найдено.")
            return
        token_short = dev["device_token"][:20] + "…"
        if data.startswith(CB_DEVICE_NAME):
            cmd_hint = f"/setname {token_short} Новое имя"
        else:
            cmd_hint = f"/setpackages {token_short} com.google.android.apps.messaging"
        text = f"Используйте команду в чате:\n<code>{_e(cmd_hint)}</code>\n\nПолный токен: <code>{_e(dev['device_token'])}</code>"
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=_device_detail_keyboard(did))
        return

    if data.startswith(CB_DEVICE_CHECK):
        try:
            did = int(data[len(CB_DEVICE_CHECK):])
        except ValueError:
            return
        dev = get_device_by_id(did)
        if not dev:
            await query.edit_message_text("Устройство не найдено.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В меню", callback_data=CB_MAIN)]]))
            return
        emoji, status_txt = _format_status(dev)
        packages = dev.get("packages") or []
        pkg_str = ", ".join(packages[:4]) + ("…" if len(packages) > 4 else "") if packages else "все"
        text = (
            f"📲 <b>{_e(dev.get('name') or 'Устройство')}</b>\n\n"
            f"{emoji} <b>Статус:</b> {status_txt}\n"
            f"Токен: <code>{_e(dev['device_token'][:24])}…</code>\n"
            f"Приложения: {_e(pkg_str)}"
        )
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=_device_detail_keyboard(did))
        return

    if data.startswith(CB_DEVICE):
        try:
            did = int(data[len(CB_DEVICE):])
        except ValueError:
            return
        devices = list_devices()
        dev = next((d for d in devices if d["id"] == did), None)
        if not dev:
            await query.edit_message_text("Устройство не найдено.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В меню", callback_data=CB_MAIN)]]))
            return
        emoji, status_txt = _format_status(dev)
        packages = dev.get("packages") or []
        pkg_str = ", ".join(packages[:4]) + ("…" if len(packages) > 4 else "") if packages else "все"
        text = (
            f"📲 <b>{_e(dev.get('name') or 'Устройство')}</b>\n\n"
            f"{emoji} <b>Статус:</b> {status_txt}\n"
            f"Токен: <code>{_e(dev['device_token'][:24])}…</code>\n"
            f"Приложения: {_e(pkg_str)}"
        )
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=_device_detail_keyboard(did))
        return

    if data == CB_HISTORY:
        text = (
            "📜 <b>История сообщений</b>\n\n"
            "Поиск по ключевым словам: отправитель, заголовок или текст уведомления.\n"
            "Например: <i>200</i>, <i>код</i>, <i>сумма</i> — найдутся все сообщения, где встречается это слово."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Поиск", callback_data=CB_SEARCH)],
            [InlineKeyboardButton("◀️ В меню", callback_data=CB_MAIN)],
        ])
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=kb)
        return

    if data == CB_SEARCH:
        context.user_data["pending_search"] = True
        await query.edit_message_text(
            "🔍 Отправьте <b>слово или число</b> для поиска (например: <code>200</code> или <code>код</code>).",
            parse_mode="HTML",
        )
        return


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    name = " ".join(context.args).strip() if context.args else "Устройство"
    token = create_device(name)
    device = get_device_by_token(token)
    if not device:
        await update.message.reply_text("Ошибка создания устройства.")
        return
    api_url = (get_settings().api_base_url or "https://ваш-сервер.com").rstrip("/")
    device_id = device["id"]
    qr_payload = f"{QR_PREFIX}\n{api_url}\n{token}"
    qr_bytes = _make_qr_bytes(qr_payload)
    await update.message.reply_photo(
        photo=qr_bytes,
        caption="📱 Отсканируйте QR в приложении EVATEAM для добавления устройства.",
    )
    await update.message.reply_text(
        f"✅ Устройство добавлено.\n\n<b>Токен</b>: <code>{_e(token)}</code>\n\n<b>Сервер</b>: <code>{_e(api_url)}</code>\n\nЗадайте имя кнопкой ниже.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Задать имя устройству", callback_data=f"{CB_SETNAME_PROMPT}{device_id}")],
            *(_main_menu_keyboard().inline_keyboard),
        ]),
    )


async def cmd_devices(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    devices = list_devices()
    if not devices:
        await update.message.reply_text("Нет устройств. Используйте кнопку «➕ Новое устройство» или /new.", reply_markup=_main_menu_keyboard())
        return
    online_count = sum(1 for d in devices if _is_online(_parse_last_seen(d.get("last_seen"))))
    text = (
        f"📱 <b>Устройства</b>\n\n"
        f"Всего: {len(devices)}  ·  В сети: {online_count} 🟢  ·  Не в сети: {len(devices) - online_count} 🔴\n\n"
        "Выберите устройство:"
    )
    await update.message.reply_text(text=text, parse_mode="HTML", reply_markup=_devices_list_keyboard())


async def cmd_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    current = get_channel_id()
    if not context.args:
        if current:
            await update.message.reply_text(f"Текущий канал: <code>{_e(current)}</code>\nИзменить: /channel -100...", parse_mode="HTML")
        else:
            await update.message.reply_text("Канал не задан. Укажите ID: /channel -1001234567890", reply_markup=_main_menu_keyboard())
        return
    new_id = " ".join(context.args).strip()
    set_channel_id(new_id)
    await update.message.reply_text(f"✅ Канал установлен: <code>{_e(new_id)}</code>", parse_mode="HTML", reply_markup=_main_menu_keyboard())


async def cmd_setname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /setname <токен> <имя>")
        return
    token = context.args[0]
    name = " ".join(context.args[1:]).strip()
    if not get_device_by_token(token):
        await update.message.reply_text("Устройство с таким токеном не найдено.")
        return
    set_device_name(token, name)
    await update.message.reply_text(f"✅ Имя обновлено: {_e(name)}")


async def cmd_setpackages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 1:
        await update.message.reply_text("Использование: /setpackages <токен> [пакет1, пакет2, ...]")
        return
    token = context.args[0]
    packages = [p.strip() for p in " ".join(context.args[1:]).split(",") if p.strip()] if len(context.args) > 1 else []
    if not get_device_by_token(token):
        await update.message.reply_text("Устройство не найдено.")
        return
    set_device_packages(token, packages)
    if packages:
        await update.message.reply_text(f"✅ Пакеты: {', '.join(packages)}")
    else:
        await update.message.reply_text("✅ Фильтр сброшен (все разрешены).")


async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 1:
        await update.message.reply_text("Использование: /delete <токен>")
        return
    token = context.args[0]
    if not delete_device(token):
        await update.message.reply_text("Устройство не найдено.")
        return
    await update.message.reply_text("✅ Устройство удалено.")


async def handle_text_for_device_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка ввода имени устройства после «Задать имя» и поиска по истории."""
    if not update.message or not update.message.text:
        return

    # Поиск по истории
    if context.user_data.get("pending_search"):
        context.user_data.pop("pending_search", None)
        keyword = (update.message.text or "").strip()
        if not keyword:
            await update.message.reply_text("Введите слово или число для поиска.")
            return
        results = search_notifications(keyword, limit=50)
        if not results:
            await update.message.reply_text(f"По запросу «{_e(keyword)}» ничего не найдено.")
            return
        lines = [f"🔍 По запросу «{_e(keyword)}» найдено {len(results)} сообщений:\n"]
        for r in results[:25]:
            device_name = _e((r.get("device_name") or "Устройство")[:20])
            sender = _e((r.get("sender") or "")[:30])
            title = _e((r.get("title") or "")[:40])
            text_preview = (r.get("text") or "")[:80].replace("\n", " ")
            text_preview = _e(text_preview)
            created = (r.get("created_at") or "")[:19]
            lines.append(f"📱 {device_name} · {created}\n{sender} / {title}\n{text_preview}…")
        if len(results) > 25:
            lines.append(f"\n… и ещё {len(results) - 25}")
        msg = "\n\n".join(lines)
        if len(msg) > 4000:
            msg = msg[:3970] + "\n\n… обрезано"
        await update.message.reply_text(msg, parse_mode="HTML")
        return

    # Имя устройства
    did = context.user_data.pop("pending_device_name", None)
    if did is None:
        return
    dev = get_device_by_id(did)
    if not dev:
        await update.message.reply_text("Устройство не найдено.")
        return
    name = (update.message.text or "").strip()[:100] or "Устройство"
    set_device_name(dev["device_token"], name)
    await update.message.reply_text(f"✅ Имя сохранено: {_e(name)}", parse_mode="HTML")


async def _job_check_offline_devices(context: ContextTypes.DEFAULT_TYPE) -> None:
    from telegram_send import send_alert_to_chat_async
    alert_chat_id = get_alert_chat_id()
    if not alert_chat_id:
        return
    for dev in get_devices_overdue_for_offline_alert():
        name = dev.get("name") or "Устройство"
        try:
            await send_alert_to_chat_async(
                alert_chat_id,
                f"⚠️ Устройство «{name}» не выходит на связь более {ONLINE_THRESHOLD_MINUTES} мин.\n\n"
                "Возможные причины: приложение закрыто или упало, нет интернета, выключен телефон. "
                "Проверьте устройство и работу EVATEAM.",
            )
            mark_device_offline_alert_sent(dev["device_token"])
        except Exception as e:
            logger.exception("Offline alert send failed for %s: %s", name, e)


def build_application() -> Application:
    settings = get_settings()
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("new", cmd_new))
    app.add_handler(CommandHandler("devices", cmd_devices))
    app.add_handler(CommandHandler("channel", cmd_channel))
    app.add_handler(CommandHandler("setname", cmd_setname))
    app.add_handler(CommandHandler("setpackages", cmd_setpackages))
    app.add_handler(CommandHandler("delete", cmd_delete))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_for_device_name),
    )
    # Проверка каждые 5 мин; алерт об офлайне только в бота (не в канал)
    if app.job_queue:
        app.job_queue.run_repeating(_job_check_offline_devices, interval=300, first=120)
    return app
