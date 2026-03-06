import logging
from datetime import datetime
from telegram import Bot
from config import get_settings

logger = logging.getLogger("telegram")
_cached_bot: Bot | None = None


def _bot() -> Bot:
    global _cached_bot
    if _cached_bot is None:
        _cached_bot = Bot(token=get_settings().telegram_bot_token)
    return _cached_bot


def _escape(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


async def send_to_channel_async(
    channel_id: str,
    device_name: str,
    package: str,
    app_name: str,
    sender: str,
    title: str,
    text: str,
) -> None:
    if not channel_id:
        return
    # Красивое форматирование: отправитель крупно, текст сообщения, источник мелко
    time_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    sender_display = _escape(sender) if sender else _escape(title)
    if not sender_display:
        sender_display = "(неизвестный отправитель)"
    body = _escape(text) if text else "—"
    message = (
        f"📩 <b>От:</b> {sender_display}\n\n"
        f"💬 <b>Сообщение:</b>\n{body}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📲 {_escape(device_name)}  ·  {_escape(app_name)}\n"
        f"🕐 {time_str}"
    )
    await _bot().send_message(
        chat_id=channel_id,
        text=message,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
