import hashlib

from pantry.contracts.auth import AuthResult
from pantry.models import Account, ApiKey


def hash_secret(secret: str) -> str:
    """Hash a high-entropy API key without retaining the plaintext."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def normalize_secret(secret: str) -> str:
    normalized = secret.strip()
    if not normalized:
        raise ValueError("API key must not be empty")
    return normalized


def key_prefix(secret: str) -> str:
    return secret[:20]


async def create_api_key(*, account: Account, name: str, secret: str) -> ApiKey:
    name = name.strip()
    if not name:
        raise ValueError("API key name must not be empty")
    secret = normalize_secret(secret)
    return await ApiKey.create(
        account=account,
        name=name,
        secret_hash=hash_secret(secret),
        key_prefix=key_prefix(secret),
    )


async def authenticate_secret(secret: str) -> AuthResult:
    secret = secret.strip()
    if not secret:
        return AuthResult(status="invalid")

    api_key = await ApiKey.get_or_none(secret_hash=hash_secret(secret)).prefetch_related("account")
    if api_key is None:
        return AuthResult(status="invalid")
    if not api_key.is_active or not api_key.account.is_active:
        return AuthResult(status="disabled")

    return AuthResult(status="authenticated", account=api_key.account, api_key=api_key)
