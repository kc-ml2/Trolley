import secrets

from pantry.contracts.api_keys import IssuedApiKey
from pantry.management.validation import require_text
from pantry.models import Account, ApiKey
from pantry.services.auth import create_api_key as persist_api_key


def serialize_api_key(api_key: ApiKey) -> dict[str, str | bool | None]:
    return {
        "id": str(api_key.id),
        "account_id": str(api_key.account.id),
        "account_name": api_key.account.name or api_key.account.email,
        "name": api_key.name,
        "key_prefix": api_key.key_prefix,
        "is_active": api_key.is_active,
    }


async def list_api_keys(account_id: str | None = None) -> list[dict[str, str | bool | None]]:
    query = ApiKey.all().prefetch_related("account")
    if account_id is not None:
        query = query.filter(account_id=account_id)
    api_keys = await query.order_by("account_id", "name")
    return [serialize_api_key(api_key) for api_key in api_keys]


async def issue_api_key(account_id: str, name: str) -> IssuedApiKey:
    account = await Account.get(id=account_id)
    secret = f"sk-pantry-{secrets.token_urlsafe(32)}"
    api_key = await persist_api_key(
        account=account,
        name=require_text(name, "name"),
        secret=secret,
    )
    return IssuedApiKey(
        id=str(api_key.id),
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        secret=secret,
        is_active=api_key.is_active,
    )


async def update_api_key(api_key_id: str, *, is_active: bool) -> dict[str, str | bool | None]:
    api_key = await ApiKey.get(id=api_key_id).prefetch_related("account")
    api_key.is_active = is_active
    await api_key.save()
    return serialize_api_key(api_key)
