from pydantic import Field
from pydantic_settings import BaseSettings


class BotSettings(BaseSettings):
    # Telegram — reads BOT_TOKEN directly
    bot_token: str = Field(default="", validation_alias="BOT_TOKEN")
    webhook_url: str = "https://localhost/bot/webhook"
    webhook_secret: str = "bot-webhook-secret"
    backend_url: str = "http://backend:8000"
    mini_app_url: str = "https://localhost/app"
    # TON network — reads from shared .core.env
    ton_network: str = Field(default="testnet", validation_alias="APP_TON_NETWORK")

    model_config = {
        "env_prefix": "BOT_",
        "env_file": ".env",
        "extra": "ignore",
    }


settings = BotSettings()
