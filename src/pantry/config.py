from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PANTRY_",
        extra="ignore",
    )

    database_url: str = "sqlite://./pantry.db"
    public_base_url: str = "http://localhost:8000"
    bootstrap_admin_email: str | None = None
    bootstrap_admin_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
