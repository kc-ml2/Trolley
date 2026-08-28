import hashlib
import secrets

from trolley.persistence.models import ApiKey, User


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def issue_secret() -> str:
    return f"sk-trolley-{secrets.token_urlsafe(32)}"


async def create_api_key(user: User, name: str, secret: str | None = None) -> tuple[ApiKey, str]:
    secret = secret or issue_secret()
    key = await ApiKey.create(
        user=user,
        name=name,
        secret_hash=hash_secret(secret),
        key_prefix=secret[:20],
    )
    return key, secret
