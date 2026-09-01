from enum import StrEnum
from functools import lru_cache
from typing import Annotated

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from trolley.auth.roles import normalize_admin_emails


class ConfigurationError(RuntimeError):
    pass


class SmtpSecurity(StrEnum):
    PLAIN = "plain"
    STARTTLS = "starttls"
    TLS = "tls"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="TROLLEY_",
        extra="ignore",
    )

    database_url: str = "sqlite://./trolley.db"
    public_base_url: str = "http://localhost:8000"
    targets_file: str = "targets.yaml"
    admin_emails: Annotated[frozenset[str], NoDecode] = frozenset()
    email_from: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_security: SmtpSecurity = SmtpSecurity.STARTTLS
    smtp_timeout: float = 10

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
    if settings.smtp_host and not settings.email_from:
        raise ConfigurationError("TROLLEY_EMAIL_FROM is required when SMTP is configured")
    if settings.email_from and not settings.smtp_host:
        raise ConfigurationError("TROLLEY_SMTP_HOST is required when email is configured")
    if bool(settings.smtp_username) != bool(settings.smtp_password):
        raise ConfigurationError(
            "TROLLEY_SMTP_USERNAME and TROLLEY_SMTP_PASSWORD must be configured together"
        )
    return settings


@lru_cache
def get_settings() -> Settings:
    return Settings()
