import os
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class ConfigurationError(RuntimeError):
    pass


class SmtpSecurity(StrEnum):
    PLAIN = "plain"
    STARTTLS = "starttls"
    TLS = "tls"


class ExportSettings(BaseModel):
    directory: str = "./trolley-exports"
    max_rows: int = Field(default=100_000, gt=0, strict=True)
    max_bytes: int = Field(default=100_000_000, gt=0, strict=True)
    timeout_seconds: int = Field(default=300, gt=0, strict=True)
    ttl_seconds: int = Field(default=3600, gt=0, strict=True)
    max_jobs: int = Field(default=10, gt=0, strict=True)


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    database_url: str = "sqlite://./trolley.db"
    public_base_url: str = "http://localhost:8000"
    targets: dict[str, dict[str, Any]] = Field(default_factory=dict)
    email_from: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_security: SmtpSecurity = SmtpSecurity.STARTTLS
    smtp_timeout: float = 10
    exports: ExportSettings = Field(default_factory=ExportSettings)


def load_settings(path: str | Path | None = None) -> Settings:
    config_path = Path(path or os.getenv("TROLLEY_CONFIG_FILE", "trolley.yaml"))
    if not config_path.exists():
        raise ConfigurationError(f"Configuration file not found: {config_path}")

    document = yaml.safe_load(config_path.read_text()) or {}
    if not isinstance(document, dict):
        raise ConfigurationError("Trolley configuration must be a YAML mapping")

    server = _mapping(document, "server")
    catalog = _mapping(document, "catalog")
    smtp = _mapping(document, "smtp")
    targets = document.get("targets", {})
    if not isinstance(targets, dict):
        raise ConfigurationError("targets must be a YAML mapping")

    try:
        return Settings(
            exports=_mapping(document, "exports"),
            public_base_url=server.get("public_base_url", "http://localhost:8000"),
            database_url=catalog.get("database_url", "sqlite://./trolley.db"),
            targets=targets,
            email_from=smtp.get("from"),
            smtp_host=smtp.get("host"),
            smtp_port=smtp.get("port", 587),
            smtp_username=smtp.get("username"),
            smtp_password=smtp.get("password"),
            smtp_security=smtp.get("security", SmtpSecurity.STARTTLS),
            smtp_timeout=smtp.get("timeout", 10),
        )
    except ValueError:
        # Pydantic diagnostics can include raw configuration values and credentials.
        raise ConfigurationError(
            "Invalid Trolley configuration; check field types and values"
        ) from None


def _mapping(document: dict[str, Any], name: str) -> dict[str, Any]:
    value = document.get(name, {})
    if not isinstance(value, dict):
        raise ConfigurationError(f"{name} must be a YAML mapping")
    return value


def validate_runtime_settings(settings: Settings) -> Settings:
    if settings.smtp_host and not settings.email_from:
        raise ConfigurationError("smtp.from is required when SMTP is configured")
    if settings.email_from and not settings.smtp_host:
        raise ConfigurationError("smtp.host is required when email is configured")
    if bool(settings.smtp_username) != bool(settings.smtp_password):
        raise ConfigurationError("smtp.username and smtp.password must be configured together")
    return settings


@lru_cache
def get_settings() -> Settings:
    return load_settings()
