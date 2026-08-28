from trolley.auth.api_keys import create_api_key
from trolley.auth.roles import normalize_email, validate_role_assignment
from trolley.config import Settings
from trolley.domain.users import UserRole
from trolley.persistence.models import User


async def bootstrap_admin(settings: Settings) -> None:
    if await User.exists():
        return
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_api_key:
        return

    email = normalize_email(settings.bootstrap_admin_email)
    validate_role_assignment(email, UserRole.ADMIN, settings.admin_emails)
    user = await User.create(
        email=email,
        name="Trolley Admin",
        role=UserRole.ADMIN,
    )
    key, _ = await create_api_key(user, "Bootstrap", secret=settings.bootstrap_admin_api_key)
    await key.save()
