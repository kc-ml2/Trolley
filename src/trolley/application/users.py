from typing import Any

from trolley.application.presenters import present_api_key, present_user
from trolley.auth.api_keys import create_api_key
from trolley.auth.roles import normalize_email, validate_role_assignment
from trolley.domain.users import UserOperationAccess, UserRole
from trolley.persistence.models import ApiKey, User


async def list_users() -> list[dict[str, Any]]:
    return [present_user(user) for user in await User.all().order_by("email")]


async def create_user(
    email: str,
    name: str,
    role: UserRole = UserRole.USER,
    *,
    admin_emails: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    email = normalize_email(email)
    validate_role_assignment(email, role, admin_emails)
    user = await User.create(email=email, name=name.strip(), role=role)
    return present_user(user)


async def update_user_access(
    email: str,
    operation_access: UserOperationAccess,
) -> dict[str, Any]:
    user = await User.get(email=normalize_email(email), is_active=True)
    user.operation_access = operation_access
    await user.save()
    return present_user(user)


async def issue_api_key(email: str, name: str) -> dict[str, Any]:
    user = await User.get(email=email.strip().lower(), is_active=True)
    key, secret = await create_api_key(user, name.strip())
    return {
        "id": str(key.id),
        "user_id": str(user.id),
        "name": key.name,
        "key_prefix": key.key_prefix,
        "secret": secret,
    }


async def list_api_keys(email: str) -> list[dict[str, Any]]:
    keys = await ApiKey.filter(user__email=email.strip().lower()).order_by("name")
    return [present_api_key(key) for key in keys]
