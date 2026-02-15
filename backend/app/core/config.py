from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    app_name: str = "Telegram Ads Marketplace"
    debug: bool = True

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/marketplace"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # Telegram — reads BOT_TOKEN (shared) or APP_BOT_TOKEN (prefixed)
    bot_token: str = Field(default="", validation_alias="BOT_TOKEN")
    mini_app_url: str = ""

    # TON
    ton_api_key: str = ""
    ton_api_base_url: str = "https://toncenter.com/api/v3"
    ton_network: str = "testnet"  # "mainnet" or "testnet"
    ton_platform_mnemonic: str = ""
    deal_expire_hours: int = 72       # Inactivity timeout for pre-escrow statuses (hours)
    deal_refund_hours: int = 48       # Post-escrow inactivity timeout before auto-refund (hours)
    platform_fee_percent: int = 10  # 0..100, platform fee on escrow release

    # Creative / Posting
    creative_retention_hours: int = 24
    posting_deadline_hours: int = 48

    # Rate limiting
    rate_limit_default: str = "60/minute"
    rate_limit_auth: str = "10/minute"
    rate_limit_escrow: str = "5/minute"

    # CORS
    cors_origins: list[str] = ["*"]

    # Security
    init_data_max_age_seconds: int = 300

    # Cache
    cache_listing_ttl: int = 60

    # MTProto (optional — for enhanced channel analytics)
    mtproto_api_id: int | None = Field(default=None, validation_alias="MTPROTO_API_ID")
    mtproto_api_hash: str | None = Field(default=None, validation_alias="MTPROTO_API_HASH")
    mtproto_session_string: str | None = Field(default=None, validation_alias="MTPROTO_SESSION_STRING")

    @property
    def mtproto_configured(self) -> bool:
        return all([self.mtproto_api_id, self.mtproto_api_hash, self.mtproto_session_string])

    model_config = {
        "env_prefix": "APP_",
        "env_file": ".env",
        "extra": "ignore",
    }


settings = Settings()
