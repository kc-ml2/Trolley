from urllib.parse import urlsplit

from pantry.management.validation import require_text
from pantry.models import Credential, Provider


def validate_base_url(base_url: str) -> str:
    normalized = require_text(base_url, "base_url").rstrip("/")
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base_url must be an absolute HTTP or HTTPS URL")
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError("base_url must not contain credentials, query, or fragment")
    return normalized


def serialize_provider(provider: Provider) -> dict[str, str | bool | None]:
    credential = provider.credential
    return {
        "id": str(provider.id),
        "name": provider.name,
        "base_url": provider.base_url,
        "credential_name": credential.name if credential else None,
        "is_active": provider.is_active,
    }


async def list_providers() -> list[dict[str, str | bool | None]]:
    providers = await Provider.all().prefetch_related("credential").order_by("name")
    return [serialize_provider(provider) for provider in providers]


async def create_provider(
    name: str,
    base_url: str,
    credential_name: str | None = None,
) -> dict[str, str | bool | None]:
    credential = (
        await Credential.get(name=require_text(credential_name, "credential_name"))
        if credential_name is not None
        else None
    )
    provider = await Provider.create(
        name=require_text(name, "name"),
        base_url=validate_base_url(base_url),
        credential=credential,
    )
    return serialize_provider(provider)


async def update_provider(
    name: str,
    *,
    base_url: str | None = None,
    credential_name: str | None = None,
    clear_credential: bool = False,
    is_active: bool | None = None,
) -> dict[str, str | bool | None]:
    if credential_name is not None and clear_credential:
        raise ValueError("credential_name and clear_credential cannot be used together")

    provider = await Provider.get(name=require_text(name, "name")).prefetch_related("credential")
    if base_url is not None:
        provider.base_url = validate_base_url(base_url)
    if credential_name is not None:
        provider.credential = await Credential.get(
            name=require_text(credential_name, "credential_name")
        )
    elif clear_credential:
        provider.credential = None
    if is_active is not None:
        provider.is_active = is_active
    await provider.save()
    await provider.fetch_related("credential")
    return serialize_provider(provider)
