from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    PROJECT_NAME: str = "AION"

    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str

    REDIS_URL: str

    OPENAI_API_KEY: str = ""

    OPENAI_MODEL: str = "gpt-4o-mini"

    # Image model for post pictures. gpt-image-1 is retired on 2026-10-23.
    OPENAI_IMAGE_MODEL: str = "gpt-image-2"
    OPENAI_IMAGE_MODEL_FALLBACK: str = "gpt-image-1.5"

    TELEGRAM_BOT_TOKEN: str = ""

    SECURITY_AUDIT_INTERVAL_SECONDS: int = 900

    INSTAGRAM_ACCESS_TOKEN: str = ""

    INSTAGRAM_BUSINESS_ACCOUNT_ID: str = ""

    INSTAGRAM_APP_SECRET: str = ""

    INSTAGRAM_APP_ID: str = "1578528073633315"

    INSTAGRAM_SUPPORT_POLL_INTERVAL_SECONDS: int = 300

    JWT_SECRET_KEY: str = ""

    JWT_ALGORITHM: str = "HS256"

    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7

    SMTP_HOST: str = ""

    SMTP_PORT: int = 587

    SMTP_USER: str = ""

    SMTP_PASSWORD: str = ""

    SMTP_FROM: str = "info@aionbusiness.uz"

    BRAVE_SEARCH_API_KEY: str = ""

    MINIMAX_API_KEY: str = ""

    PUBLIC_BASE_URL: str = "https://aionbusiness.uz"

    # Customer-facing Telegram bot that opens the ordering Mini App (a different
    # bot from the internal AION one). Mini App sign-in is validated with its token.
    SHOP_BOT_TOKEN: str = ""

    # Company whose menu the Mini App shows when no ?c= is given.
    SHOP_COMPANY_ID: int = 2

    # Click merchant (Shop API) credentials; online payment is offered only when all three are set.
    CLICK_SERVICE_ID: str = ""
    CLICK_MERCHANT_ID: str = ""
    CLICK_SECRET_KEY: str = ""
    CLICK_MERCHANT_USER_ID: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
    )


@lru_cache
def get_settings():

    return Settings()


settings = get_settings()