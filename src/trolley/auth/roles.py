from collections.abc import Iterable

from trolley.domain.users import UserRole


def normalize_email(email: str) -> str:
    return email.strip().lower()


def normalize_admin_emails(emails: Iterable[str]) -> frozenset[str]:
    return frozenset(normalize_email(email) for email in emails if email.strip())


def effective_role(
    email: str,
    stored_role: UserRole,
    admin_emails: frozenset[str],
) -> UserRole:
    if stored_role == UserRole.ADMIN and normalize_email(email) in admin_emails:
        return UserRole.ADMIN
    return UserRole.USER


def validate_role_assignment(
    email: str,
    role: UserRole,
    admin_emails: frozenset[str],
) -> None:
    if role == UserRole.ADMIN and normalize_email(email) not in admin_emails:
        raise PermissionError("Email is not allowed to receive the admin role")
