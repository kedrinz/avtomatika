#!/usr/bin/env python3
"""
Запуск API и бота в одном процессе.
Для продакшена предпочтительно запускать раздельно: uvicorn api:app + python run_bot.py
"""
import asyncio
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
    app = build_application()
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    # В Python 3.12+ в главном потоке нет event loop — создаём для run_polling()
    asyncio.set_event_loop(asyncio.new_event_loop())
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    logger.info("API started on http://0.0.0.0:8000")
    run_bot()
