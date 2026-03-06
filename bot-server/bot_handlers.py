import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
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


def _escape(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user:
        return
    text = (
        "👋 <b>Уведомления в Telegram</b>\n\n"
        "Команды:\n"
        "/start — это сообщение\n"
        "/new — добавить устройство (получить токен)\n"
        "/devices — список устройств\n"
        "/channel — показать/установить канал для уведомлений\n"
        "/setname &lt;токен&gt; &lt;имя&gt; — имя устройства\n"
        "/setpackages &lt;токен&gt; &lt;пакеты через запятую&gt; — фильтр приложений (пусто = все)\n"
        "/delete &lt;токен&gt; — удалить устройство\n"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    name = " ".join(context.args).strip() if context.args else "Устройство"
    token = create_device(name)
    await update.message.reply_text(
        f"✅ Устройство добавлено.\n\n"
        f"<b>Токен</b> (введите в приложение на телефоне):\n"
        f"<code>{_escape(token)}</code>\n\n"
        f"Сервер: <code>{_escape(get_settings().api_base_url or 'https://ваш-сервер.com')}</code>",
        parse_mode="HTML",
    )


async def cmd_devices(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    devices = list_devices()
    if not devices:
        await update.message.reply_text("Нет устройств. Используйте /new чтобы добавить.")
        return
    lines = []
    for d in devices:
        packages = d.get("packages") or []
        pkg_str = ", ".join(packages[:3]) + ("…" if len(packages) > 3 else "") if packages else "все"
        lines.append(
            f"• {_escape(d['name'])} — <code>{_escape(d['device_token'][:12])}…</code> (пакеты: {_escape(pkg_str)})"
        )
    await update.message.reply_text(
        "📱 Устройства:\n\n" + "\n".join(lines),
        parse_mode="HTML",
    )


async def cmd_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    current = get_channel_id()
    if not context.args:
        if current:
            await update.message.reply_text(f"Текущий канал: <code>{_escape(current)}</code>", parse_mode="HTML")
        else:
            await update.message.reply_text(
                "Канал не задан. Укажите ID или @username: /channel -1001234567890"
            )
        return
    new_id = " ".join(context.args).strip()
    set_channel_id(new_id)
    await update.message.reply_text(f"✅ Канал установлен: <code>{_escape(new_id)}</code>", parse_mode="HTML")


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
    await update.message.reply_text(f"✅ Имя обновлено: {_escape(name)}")


async def cmd_setpackages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 1:
        await update.message.reply_text(
            "Использование: /setpackages <токен> [пакет1, пакет2, ...]\n"
            "Пустой список = перехватывать все приложения (фильтр на стороне приложения)."
        )
        return
    token = context.args[0]
    packages = [p.strip() for p in " ".join(context.args[1:]).split(",") if p.strip()] if len(context.args) > 1 else []
    if not get_device_by_token(token):
        await update.message.reply_text("Устройство с таким токеном не найдено.")
        return
    set_device_packages(token, packages)
    if packages:
        await update.message.reply_text(f"✅ Пакеты: {', '.join(packages)}")
    else:
        await update.message.reply_text("✅ Фильтр пакетов сброшен (все разрешены на стороне сервера).")


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
    return app
