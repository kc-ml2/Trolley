"""Operation execution inherits group Target access; legacy grants are ignored."""

from trolley.application.target_access import member_target_names
from trolley.auth.context import AuthContext
from trolley.persistence.models import Operation


async def accessible_operation_names(context: AuthContext) -> set[str]:
    allowed = await member_target_names(context)
    return set(
        await Operation.filter(
            is_active=True, target__is_active=True, target__name__in=allowed
        ).values_list("name", flat=True)
    )


async def can_access_operation(context: AuthContext, operation: Operation) -> bool:
    return operation.name in await accessible_operation_names(context)
