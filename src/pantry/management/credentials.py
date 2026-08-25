import os

from pantry.management.validation import require_env_name, require_text
from pantry.models import Credential


def serialize_credential(credential: Credential) -> dict[str, str | bool]:
    return {
        "id": str(credential.id),
        "name": credential.name,
        "secret_env": credential.secret_env,
        "secret_configured": bool(os.getenv(credential.secret_env)),
        "is_active": credential.is_active,
    }


async def list_credentials() -> list[dict[str, str | bool]]:
    credentials = await Credential.all().order_by("name")
    return [serialize_credential(credential) for credential in credentials]


async def create_credential(name: str, secret_env: str) -> dict[str, str | bool]:
    credential = await Credential.create(
        name=require_text(name, "name"),
        secret_env=require_env_name(secret_env),
    )
    return serialize_credential(credential)


async def update_credential(
    name: str,
    *,
    secret_env: str | None = None,
    is_active: bool | None = None,
) -> dict[str, str | bool]:
    credential = await Credential.get(name=require_text(name, "name"))
    if secret_env is not None:
        credential.secret_env = require_env_name(secret_env)
    if is_active is not None:
        credential.is_active = is_active
    await credential.save()
    return serialize_credential(credential)
