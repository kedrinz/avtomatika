#!/usr/bin/env python3
"""
Запуск API и бота в одном процессе.
Для продакшена предпочтительно запускать раздельно: uvicorn api:app + python run_bot.py
"""
import asyncio

# Критично: задать event loop ДО импорта uvicorn (он тянет uvloop и ломает get_event_loop в Python 3.12+)
def _make_loop():
    try:
        import uvloop
        return uvloop.new_event_loop()
    except ImportError:
        return asyncio.new_event_loop()

_loop = _make_loop()
asyncio.set_event_loop(_loop)

import logging
import threading
import uvicorn

from bot_handlers import build_application

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("main")


def run_api():
    uvicorn.run("api:app", host="0.0.0.0", port=8000, log_level="info")


def run_bot():
    # На всякий случай: если в текущем потоке нет loop (например, старый деплой)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        try:
            asyncio.get_event_loop()
        except RuntimeError:
            asyncio.set_event_loop(_make_loop())
    app = build_application()
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    logger.info("API started on http://0.0.0.0:8000")
    run_bot()
