import logging
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
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


async def send_to_channel_async(
    channel_id: str,
    device_name: str,
    package: str,
    app_name: str,
    title: str,
    text: str,
) -> None:
    if not channel_id:
        return
    message = (
        f"📱 <b>{app_name}</b> ({package})\n"
        f"📲 Устройство: {device_name}\n\n"
        f"<b>{_escape(title)}</b>\n\n"
        f"{_escape(text)}"
    )
    await _bot().send_message(
        chat_id=channel_id,
        text=message,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
