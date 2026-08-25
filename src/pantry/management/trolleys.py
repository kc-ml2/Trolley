import secrets

from tortoise.transactions import in_transaction

from pantry.contracts.trolleys import CreatedTrolley
from pantry.domain.accounts import AccountKind, AccountRole
from pantry.management.validation import require_text
from pantry.models import Account, ApiKey, Trolley
from pantry.services.auth import hash_secret, key_prefix


def serialize_trolley(trolley: Trolley) -> dict:
    return {
        "id": str(trolley.id),
        "account_id": str(trolley.account.id),
        "name": trolley.name,
        "version": trolley.version,
        "runtime_info": trolley.runtime_info,
        "metrics": trolley.metrics,
        "agents": trolley.agents,
        "last_seen_at": trolley.last_seen_at.isoformat() if trolley.last_seen_at else None,
        "is_active": trolley.is_active,
    }


async def list_trolleys() -> list[dict]:
    trolleys = await Trolley.all().prefetch_related("account").order_by("name")
    return [serialize_trolley(trolley) for trolley in trolleys]


async def create_trolley(name: str) -> CreatedTrolley:
    name = require_text(name, "name")
    secret = f"sk-pantry-{secrets.token_urlsafe(32)}"
    async with in_transaction() as connection:
        account = await Account.create(
            kind=AccountKind.TROLLEY,
            name=name,
            role=AccountRole.USER,
            using_db=connection,
        )
        trolley = await Trolley.create(
            account=account,
            name=name,
            using_db=connection,
        )
        await ApiKey.create(
            account=account,
            name="Trolley Runtime",
            secret_hash=hash_secret(secret),
            key_prefix=key_prefix(secret),
            using_db=connection,
        )
    return CreatedTrolley(
        id=str(trolley.id),
        account_id=str(account.id),
        name=trolley.name,
        api_key=secret,
    )


async def update_trolley(
    name: str,
    *,
    is_active: bool | None = None,
) -> dict:
    trolley = await Trolley.get(name=require_text(name, "name")).prefetch_related("account")
    if is_active is not None:
        trolley.is_active = is_active
        trolley.account.is_active = is_active
        await trolley.account.save()
    await trolley.save()
    return serialize_trolley(trolley)
