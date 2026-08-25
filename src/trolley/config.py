from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TrolleySettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    pantry_url: str = Field(validation_alias="PANTRY_URL")
    pantry_api_key: str = Field(validation_alias="PANTRY_API_KEY")
    heartbeat_interval: float = Field(
        default=60,
        gt=0,
        validation_alias="TROLLEY_HEARTBEAT_INTERVAL",
    )

    @field_validator("pantry_url")
    @classmethod
    def validate_pantry_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https", "ws", "wss"} or not parsed.netloc:
            raise ValueError("PANTRY_URL must be an absolute HTTP(S) or WS(S) URL")
        if parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ValueError("PANTRY_URL must not contain credentials, query, or fragment")
        return normalized
