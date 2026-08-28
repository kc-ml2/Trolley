from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from trolley.auth.roles import normalize_admin_emails


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="TROLLEY_",
        extra="ignore",
    )

    database_url: str = "sqlite://./trolley.db"
    public_base_url: str = "http://localhost:8000"
    admin_emails: frozenset[str] = frozenset()
    bootstrap_admin_email: str | None = None
    bootstrap_admin_api_key: str | None = None

    @field_validator("admin_emails", mode="before")
    @classmethod
    def parse_admin_emails(cls, value: object) -> frozenset[str]:
        if value is None or value == "":
            return frozenset()
        if isinstance(value, str):
            return normalize_admin_emails(value.split(","))
        return normalize_admin_emails(value)


@lru_cache
def get_settings() -> Settings:
    return Settings()
