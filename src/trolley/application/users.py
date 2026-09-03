from typing import Any

from trolley.application.presenters import present_api_key, present_user
from trolley.auth.api_keys import create_api_key
from trolley.auth.roles import normalize_email, validate_role_assignment
from trolley.domain.users import UserOperationAccess, UserRole
from trolley.email import EmailService
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


async def invite_user(
    email: str,
    name: str,
    key_name: str,
    email_service: EmailService,
    onboarding_url: str,
    *,
    admin_emails: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    email = normalize_email(email)
    role = UserRole.ADMIN if email in admin_emails else UserRole.USER
    user = await User.get_or_none(email=email)
    if user is None:
        user = await User.create(email=email, name=name.strip(), role=role)
    elif not user.is_active:
        raise ValueError("Only an active user can be invited")
    elif user.role == UserRole.ADMIN and role != UserRole.ADMIN:
        raise PermissionError("Admin email is not in TROLLEY_ADMIN_EMAILS")
    elif user.role != role:
        user.role = role
        await user.save()

    key, secret = await create_api_key(user, key_name.strip())
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

    return {
        "user": present_user(user),
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
