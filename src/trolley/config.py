from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from trolley.auth.roles import normalize_admin_emails


class ConfigurationError(RuntimeError):
    pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="TROLLEY_",
        extra="ignore",
    )

    database_url: str = "sqlite://./trolley.db"
    public_base_url: str = "http://localhost:8000"
    admin_emails: Annotated[frozenset[str], NoDecode] = frozenset()

    @field_validator("admin_emails", mode="before")
    @classmethod
    def parse_admin_emails(cls, value: object) -> frozenset[str]:
        if value is None or value == "":
            return frozenset()
        if isinstance(value, str):
            return normalize_admin_emails(value.split(","))
        return normalize_admin_emails(value)


def validate_runtime_settings(settings: Settings) -> Settings:
    if not settings.admin_emails:
        raise ConfigurationError(
            "TROLLEY_ADMIN_EMAILS must contain at least one administrator email"
        )
    return settings


@lru_cache
def get_settings() -> Settings:
    return Settings()
