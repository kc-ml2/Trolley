import re

_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def require_text(value: str, field: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field} must not be empty")
    return normalized


def require_env_name(value: str) -> str:
    normalized = require_text(value, "secret_env")
    if not _ENV_NAME.fullmatch(normalized):
        raise ValueError("secret_env must be a valid environment variable name")
    return normalized
