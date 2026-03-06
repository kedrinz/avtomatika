#!/usr/bin/env python3
import logging
from bot_handlers import build_application

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("bot")

if __name__ == "__main__":
    app = build_application()
    logger.info("Bot polling started")
    app.run_polling(allowed_updates=["message", "callback_query"])
