from trolley.auth.context import AuthContext
from trolley.domain.operations import OperationAccess
from trolley.domain.users import UserOperationAccess, UserRole
from trolley.persistence.models import Operation, OperationGrant, User


async def accessible_operation_names(context: AuthContext) -> set[str]:
    if context.role == UserRole.ADMIN:
        return set(
            await Operation.filter(is_active=True, target__is_active=True).values_list(
                "name", flat=True
            )
        )

    user = await User.get(id=context.user_id, is_active=True)
    granted_names = set(
        await OperationGrant.filter(
            user=user,
            operation__is_active=True,
            operation__target__is_active=True,
        )
        .exclude(operation__access=OperationAccess.ADMIN)
        .values_list("operation__name", flat=True)
    )
    if user.operation_access == UserOperationAccess.ASSIGNED_ONLY:
        return granted_names

    public_names = set(
        await Operation.filter(
            is_active=True,
            target__is_active=True,
            access=OperationAccess.USER,
        ).values_list("name", flat=True)
    )
    return public_names | granted_names


async def can_access_operation(context: AuthContext, operation: Operation) -> bool:
    if context.role == UserRole.ADMIN:
        return True
    if operation.access == OperationAccess.ADMIN:
        return False

    user = await User.get(id=context.user_id, is_active=True)
    has_grant = await OperationGrant.exists(user=user, operation=operation)
    if user.operation_access == UserOperationAccess.ASSIGNED_ONLY:
        return has_grant
    if operation.access == OperationAccess.USER:
        return True
    return has_grant
