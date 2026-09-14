"""Owner-only execution status across inline and file Operations."""

from uuid import UUID

from trolley.application.access import can_access_operation
from trolley.auth.context import AuthContext
from trolley.auth.roles import effective_role
from trolley.persistence.models import ApiKey, Execution


async def get_execution(execution_id: str, context: AuthContext, settings, export_manager) -> dict:
    try:
        identifier = UUID(execution_id)
    except ValueError as error:
        raise ValueError("Execution not found") from error
    key = await ApiKey.get_or_none(
        id=context.api_key_id, user_id=context.user_id, is_active=True
    ).prefetch_related("user")
    if key is None or not key.user.is_active:
        raise PermissionError("Execution access denied")
    current = AuthContext(
        str(key.user.id),
        str(key.id),
        effective_role(key.user.email, key.user.role, settings.admin_emails),
    )
    execution = await Execution.get_or_none(
        id=identifier, requested_by=context.user_id
    ).prefetch_related("operation__target")
    if execution is None:
        if export_manager is None:
            raise ValueError("Execution not found")
        job = await export_manager.get(execution_id, current)
        return export_manager.present(job)
    operation = execution.operation
    if (
        not operation.is_active
        or not operation.target.is_active
        or not await can_access_operation(current, operation)
    ):
        raise PermissionError("Execution access denied")
    # Results may reflect older SQL/permissions: do not replay stored result bodies.
    return {
        "execution_id": str(execution.id),
        "output": "inline",
        "status": execution.status,
        "created_at": execution.created_at.isoformat(),
        "finished_at": execution.finished_at.isoformat() if execution.finished_at else None,
    }
