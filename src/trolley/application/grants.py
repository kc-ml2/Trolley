from typing import Any

from trolley.auth.roles import normalize_email
from trolley.domain.operations import OperationAccess
from trolley.persistence.models import Operation, OperationGrant, User


def present_grant(grant: OperationGrant) -> dict[str, Any]:
    return {
        "id": str(grant.id),
        "email": grant.user.email,
        "operation": grant.operation.name,
        "created_at": grant.created_at.isoformat(),
    }


async def grant_operation(email: str, operation_name: str) -> dict[str, Any]:
    user = await User.get(email=normalize_email(email), is_active=True)
    operation = await Operation.get(name=operation_name, is_active=True, target__is_active=True)
    if operation.access == OperationAccess.ADMIN:
        raise ValueError("Admin operations cannot be granted to users")
    grant, _ = await OperationGrant.get_or_create(user=user, operation=operation)
    grant.user = user
    grant.operation = operation
    return present_grant(grant)


async def revoke_operation(email: str, operation_name: str) -> dict[str, Any]:
    user = await User.get(email=normalize_email(email))
    operation = await Operation.get(name=operation_name)
    deleted = await OperationGrant.filter(user=user, operation=operation).delete()
    return {
        "email": user.email,
        "operation": operation.name,
        "revoked": bool(deleted),
    }


async def list_operation_grants(
    operation_name: str | None = None,
    email: str | None = None,
) -> list[dict[str, Any]]:
    query = OperationGrant.all()
    if operation_name is not None:
        query = query.filter(operation__name=operation_name)
    if email is not None:
        query = query.filter(user__email=normalize_email(email))
    grants = await query.prefetch_related("user", "operation").order_by(
        "operation__name", "user__email"
    )
    return [present_grant(grant) for grant in grants]
