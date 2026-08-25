from pantry.domain.accounts import AccountKind, AccountRole
from pantry.management.validation import require_text
from pantry.models import Account


def validate_account(
    kind: AccountKind,
    email: str | None,
    name: str | None,
    role: AccountRole,
) -> tuple[str | None, str | None]:
    email = require_text(email, "email") if email is not None else None
    name = require_text(name, "name") if name is not None else None
    if kind == AccountKind.HUMAN and not email:
        raise ValueError("human accounts require an email")
    if kind == AccountKind.TROLLEY and not name:
        raise ValueError("trolley accounts require a name")
    if kind == AccountKind.TROLLEY and role == AccountRole.ADMIN:
        raise ValueError("trolley accounts cannot be admins")
    return email, name


def serialize_account(account: Account) -> dict[str, str | bool | None]:
    return {
        "id": str(account.id),
        "kind": account.kind.value,
        "email": account.email,
        "name": account.name,
        "role": account.role.value,
        "is_active": account.is_active,
    }


async def list_accounts() -> list[dict[str, str | bool | None]]:
    accounts = await Account.all().order_by("kind", "email", "name")
    return [serialize_account(account) for account in accounts]


async def create_account(
    kind: AccountKind,
    *,
    email: str | None = None,
    name: str | None = None,
    role: AccountRole = AccountRole.USER,
) -> dict[str, str | bool | None]:
    if kind == AccountKind.TROLLEY:
        raise ValueError("use create_trolley to create trolley accounts")
    email, name = validate_account(kind, email, name, role)
    account = await Account.create(kind=kind, email=email, name=name, role=role)
    return serialize_account(account)


async def update_account(
    account_id: str,
    *,
    email: str | None = None,
    name: str | None = None,
    role: AccountRole | None = None,
    is_active: bool | None = None,
) -> dict[str, str | bool | None]:
    account = await Account.get(id=account_id)
    if account.kind == AccountKind.TROLLEY:
        raise ValueError("use update_trolley to update trolley accounts")
    next_email = email if email is not None else account.email
    next_name = name if name is not None else account.name
    next_role = role if role is not None else account.role
    next_email, next_name = validate_account(account.kind, next_email, next_name, next_role)
    account.email = next_email
    account.name = next_name
    account.role = next_role
    if is_active is not None:
        account.is_active = is_active
    await account.save()
    return serialize_account(account)
