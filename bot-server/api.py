from fastapi import FastAPI, HTTPException, Header, Request
from pydantic import BaseModel
import logging

from config import get_settings
from database import get_device_by_token, get_channel_id, update_device_last_seen, save_notification
from telegram_send import send_to_channel_async, send_alert_to_channel_async

logger = logging.getLogger("api")
app = FastAPI(title="Notify to Telegram API", version="1.0")


class NotifyPayload(BaseModel):
    device_token: str
    package: str
    app_name: str
    title: str
    text: str
    sender: str | None = None  # имя/номер отправителя (для SMS)


class PingPayload(BaseModel):
    device_token: str


@app.post("/api/ping")
async def api_ping(
    payload: PingPayload,
    request: Request,
    x_api_key: str | None = Header(None, alias="X-Api-Key"),
):
    """Обновляет last_seen устройства без отправки в канал. Вызывается приложением при сохранении настроек."""
    _check_api_secret(request, x_api_key)
    device = get_device_by_token(payload.device_token)
    if not device:
        raise HTTPException(status_code=403, detail="Unknown device token")
    update_device_last_seen(payload.device_token)
    return {"ok": True}


def _check_api_secret(request: Request, x_api_key: str | None = None) -> None:
    secret = get_settings().api_secret
    if not secret:
        return
    if not x_api_key or x_api_key.strip() != secret:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Api-Key")


@app.post("/api/notify")
async def api_notify(
    payload: NotifyPayload,
    request: Request,
    x_api_key: str | None = Header(None, alias="X-Api-Key"),
):
    _check_api_secret(request, x_api_key)
    device = get_device_by_token(payload.device_token)
    if not device:
        raise HTTPException(status_code=403, detail="Unknown device token")
    # Обновляем last_seen и проверяем, было ли устройство «офлайн» (тогда отправим «снова в сети»)
    came_back_online = update_device_last_seen(payload.device_token)
    packages = device.get("packages") or []
    if packages and payload.package not in packages:
        raise HTTPException(status_code=400, detail="Package not allowed for this device")
    channel = get_channel_id()
    if not channel:
        logger.warning("Channel ID not set; notification not sent")
        return {"ok": True, "sent": False}
    try:
        await send_to_channel_async(
            channel_id=channel,
            device_name=device.get("name", "Устройство"),
            package=payload.package,
            app_name=payload.app_name,
            sender=payload.sender or payload.title or "",
            title=payload.title or "(без заголовка)",
            text=payload.text or "",
        )
        save_notification(
            device_token=payload.device_token,
            device_name=device.get("name", "Устройство"),
            package=payload.package,
            app_name=payload.app_name,
            sender=payload.sender or payload.title or "",
            title=payload.title or "(без заголовка)",
            text=payload.text or "",
        )
        if came_back_online:
            try:
                await send_alert_to_channel_async(
                    f"✅ Устройство «{device.get('name', 'Устройство')}» снова в сети."
                )
            except Exception as e:
                logger.exception("Failed to send 'back online' alert: %s", e)
        return {"ok": True, "sent": True}
    except Exception as e:
        logger.exception("Send to Telegram failed: %s", e)
        raise HTTPException(status_code=502, detail="Failed to send to Telegram")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
