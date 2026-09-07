from typing import Any

from tortoise.transactions import in_transaction

from trolley.application.groups import resolve_groups
from trolley.application.presenters import present_api_key, present_user
from trolley.auth.api_keys import create_api_key
from trolley.auth.roles import normalize_email, validate_role_assignment
from trolley.domain.users import UserOperationAccess, UserRole
from trolley.email import EmailService
from trolley.persistence.models import ApiKey, GroupMembership, User


async def list_users() -> list[dict[str, Any]]:
    return [present_user(user) for user in await User.all().order_by("email")]


async def create_user(
    email: str,
    name: str,
    role: UserRole = UserRole.USER,
    *,
    admin_emails: frozenset[str] = frozenset(),
    group_names: list[str] | None = None,
) -> dict[str, Any]:
    email = normalize_email(email)
    validate_role_assignment(email, role, admin_emails)
    async with in_transaction():
        selected = await resolve_groups(group_names or [])
        user = await User.create(email=email, name=name.strip(), role=role)
        for group in selected:
            await GroupMembership.get_or_create(user=user, group=group)
    return {**present_user(user), "groups": sorted({g.name for g in selected})}


async def invite_user(
    email: str,
    name: str,
    key_name: str,
    email_service: EmailService,
    onboarding_url: str,
    *,
    admin_emails: frozenset[str] = frozenset(),
    group_names: list[str] | None = None,
) -> dict[str, Any]:
    selected = await resolve_groups(group_names or [])
    email = normalize_email(email)
    role = UserRole.ADMIN if email in admin_emails else UserRole.USER
    user = await User.get_or_none(email=email)
    if user is None:
        user = await User.create(email=email, name=name.strip(), role=UserRole.USER)
    elif not user.is_active:
        raise ValueError("Only an active user can be invited")
    elif user.role == UserRole.ADMIN and role != UserRole.ADMIN:
        raise PermissionError("Admin email is not in admins.emails")

    # Deliver an inactive key. Only activate it together with the role and
    # memberships after delivery; crashes/failures leave no usable new key.
    key, secret = await create_api_key(user, key_name.strip(), is_active=False)
    try:
        await email_service.send(
            user.email,
            "You have been invited to Trolley",
            f"""Hello {user.name},

You have been invited to Trolley.

API key: {secret}

Treat this key like a password. Do not paste it into an agent conversation.
Enter it directly in your MCP client's secret settings or a local
TROLLEY_API_KEY environment variable.

Onboarding instructions: {onboarding_url}
""",
        )
    except Exception:
        key.is_active = False
        await key.save()
        raise

    # Email cannot be rolled back. If finalization fails the delivered key stays
    # inactive, while role and membership changes roll back atomically.
    async with in_transaction():
        user = await User.filter(id=user.id, is_active=True).select_for_update().get()
        selected = await resolve_groups(group_names or [])
        user.role = role
        await user.save(update_fields=["role"])
        for group in selected:
            await GroupMembership.get_or_create(user=user, group=group)
        key.is_active = True
        await key.save(update_fields=["is_active"])
    memberships = (
        await GroupMembership.filter(user=user)
        .order_by("group__name")
        .values_list("group__name", flat=True)
    )
    return {
        "user": {**present_user(user), "groups": memberships},
        "api_key": present_api_key(key),
        "email_sent": True,
    }


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
