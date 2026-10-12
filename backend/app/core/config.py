from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    PROJECT_NAME: str = "AION"

    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str

    REDIS_URL: str

    OPENAI_API_KEY: str = ""

    OPENAI_MODEL: str = "gpt-4o-mini"

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

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
    )


@lru_cache
def get_settings():

    return Settings()


settings = get_settings()