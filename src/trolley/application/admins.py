from trolley.auth.roles import normalize_email
from trolley.domain.users import UserRole
from trolley.persistence.models import User


async def ensure_admin_users(admin_emails: frozenset[str]) -> list[User]:
    if not admin_emails:
        return []

    existing_admins = await User.filter(role=UserRole.ADMIN, is_active=True)
    if any(normalize_email(user.email) in admin_emails for user in existing_admins):
        return []

    ensured = []
    for email in sorted(admin_emails):
        user = await User.get_or_none(email=email)
        if user is None:
            user = await User.create(
                email=email,
                name=email,
                role=UserRole.ADMIN,
            )
        else:
            user.role = UserRole.ADMIN
            user.is_active = True
            await user.save()
        ensured.append(user)
    return ensured
