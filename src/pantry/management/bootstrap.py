from tortoise.transactions import in_transaction

from pantry.config import Settings
from pantry.domain.accounts import AccountKind, AccountRole
from pantry.models import Account, ApiKey
from pantry.services.auth import hash_secret, key_prefix, normalize_secret


async def bootstrap_admin(settings: Settings) -> bool:
    email = settings.bootstrap_admin_email
    secret = settings.bootstrap_admin_api_key
    if bool(email) != bool(secret):
        raise ValueError(
            "PANTRY_BOOTSTRAP_ADMIN_EMAIL and PANTRY_BOOTSTRAP_ADMIN_API_KEY must be set together"
        )
    if not email or not secret:
        return False
    secret = normalize_secret(secret)

    async with in_transaction() as connection:
        if await Account.all().using_db(connection).exists():
            return False
        admin = await Account.create(
            kind=AccountKind.HUMAN,
            email=email,
            role=AccountRole.ADMIN,
            using_db=connection,
        )
        await ApiKey.create(
            account=admin,
            name="Bootstrap Admin",
            secret_hash=hash_secret(secret),
            key_prefix=key_prefix(secret),
            using_db=connection,
        )
    return True
