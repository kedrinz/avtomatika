import os
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    telegram_bot_token: str = ""
    telegram_channel_id: str = ""  # ID канала (например -1001234567890) или @channel
    database_path: str = "data/bot.db"
    api_secret: str = ""  # опционально: заголовок X-Api-Key для защиты API
    api_base_url: str = ""  # URL сервера для подсказки в боте (например https://your-server.com)

    model_config = {"env_file": ".env", "extra": "ignore"}

    @field_validator("telegram_bot_token")
    @classmethod
    def token_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("TELEGRAM_BOT_TOKEN обязателен")
        return v.strip()

    @field_validator("telegram_channel_id")
    @classmethod
    def channel_optional(cls, v: str) -> str:
        return (v or "").strip()


def get_settings() -> Settings:
    return Settings()
