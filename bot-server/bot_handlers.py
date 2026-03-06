import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import get_settings
from database import (
    create_device,
    list_devices,
    get_device_by_token,
    set_device_name,
    set_device_packages,
    delete_device,
    get_channel_id,
    set_channel_id,
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


def _e(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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
            InlineKeyboardButton("➕ Новое устройство", callback_data=CB_NEW),
        ],
    ])


def _devices_list_keyboard() -> InlineKeyboardMarkup:
    devices = list_devices()
    buttons = []
    for d in devices:
        name = (d.get("name") or "Устройство")[:25]
        buttons.append([InlineKeyboardButton(f"📲 {_e(name)}", callback_data=f"{CB_DEVICE}{d['id']}")])
    buttons.append([InlineKeyboardButton("◀️ В меню", callback_data=CB_MAIN)])
    return InlineKeyboardMarkup(buttons)


def _device_detail_keyboard(device_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ Имя", callback_data=f"{CB_DEVICE_NAME}{device_id}"),
            InlineKeyboardButton("📦 Приложения", callback_data=f"{CB_DEVICE_PKG}{device_id}"),
        ],
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
            text = "📱 <b>Устройства</b>\n\nВыберите устройство:"
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
        text = "⚙️ <b>Настройки</b>\n\nВыберите параметр:"
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=_settings_keyboard())
        return

    if data == CB_NEW:
        name = "Устройство"
        token = create_device(name)
        api_url = get_settings().api_base_url or "https://ваш-сервер.com"
        text = (
            "✅ <b>Устройство добавлено</b>\n\n"
            f"<b>Токен</b> (введите в приложении на телефоне):\n<code>{_e(token)}</code>\n\n"
            f"<b>URL сервера</b> в приложении:\n<code>{_e(api_url)}</code>\n\n"
            "В приложении: добавьте приложение «Сообщения» для SMS и при необходимости настройте «От кого принимать»."
        )
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 К списку устройств", callback_data=CB_DEVICES)],
            [InlineKeyboardButton("◀️ В меню", callback_data=CB_MAIN)],
        ]))
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
        packages = dev.get("packages") or []
        pkg_str = ", ".join(packages[:4]) + ("…" if len(packages) > 4 else "") if packages else "все"
        text = (
            f"📲 <b>{_e(dev.get('name') or 'Устройство')}</b>\n\n"
            f"Токен: <code>{_e(dev['device_token'][:24])}…</code>\n"
            f"Приложения: {_e(pkg_str)}"
        )
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=_device_detail_keyboard(did))
        return


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    name = " ".join(context.args).strip() if context.args else "Устройство"
    token = create_device(name)
    api_url = get_settings().api_base_url or "https://ваш-сервер.com"
    await update.message.reply_text(
        f"✅ Устройство добавлено.\n\n"
        f"<b>Токен</b>:\n<code>{_e(token)}</code>\n\n"
        f"<b>Сервер</b>: <code>{_e(api_url)}</code>",
        parse_mode="HTML",
        reply_markup=_main_menu_keyboard(),
    )


async def cmd_devices(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    devices = list_devices()
    if not devices:
        await update.message.reply_text("Нет устройств. Используйте кнопку «➕ Новое устройство» или /new.", reply_markup=_main_menu_keyboard())
        return
    text = "📱 <b>Устройства</b>\n\nВыберите устройство:"
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
    return app
