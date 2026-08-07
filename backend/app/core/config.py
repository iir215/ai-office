from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    PROJECT_NAME: str = "AION"

    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str

    REDIS_URL: str

    OPENAI_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
    )


@lru_cache
def get_settings():

    return Settings()


settings = get_settings()