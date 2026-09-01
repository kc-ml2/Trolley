from typing import Any
from uuid import UUID

from trolley.auth.context import AuthContext
from trolley.domain.operation_requests import OperationRequestStatus
from trolley.persistence.models import Operation, OperationRequest, User


def present_operation_request(request: OperationRequest) -> dict[str, Any]:
    return {
        "id": str(request.id),
        "requested_by": request.requested_by.email,
        "title": request.title,
        "description": request.description,
        "reason": request.reason,
        "status": request.status,
        "operation": request.operation.name if request.operation else None,
        "admin_note": request.admin_note,
        "created_at": request.created_at.isoformat(),
        "updated_at": request.updated_at.isoformat(),
    }


async def request_operation(
    title: str,
    description: str,
    reason: str,
    context: AuthContext,
) -> dict[str, Any]:
    user = await User.get(id=UUID(context.user_id), is_active=True)
    request = await OperationRequest.create(
        requested_by=user,
        title=title.strip(),
        description=description.strip(),
        reason=reason.strip(),
    )
    request.requested_by = user
    request.operation = None
    return present_operation_request(request)


async def list_my_operation_requests(context: AuthContext) -> list[dict[str, Any]]:
    requests = (
        await OperationRequest.filter(requested_by_id=UUID(context.user_id))
        .prefetch_related("requested_by", "operation")
        .order_by("-created_at")
    )
    return [present_operation_request(request) for request in requests]


async def list_operation_requests(
    status: OperationRequestStatus | None = None,
) -> list[dict[str, Any]]:
    query = OperationRequest.all()
    if status is not None:
        query = query.filter(status=status)
    requests = await query.prefetch_related("requested_by", "operation").order_by("-created_at")
    return [present_operation_request(request) for request in requests]


async def resolve_operation_request(
    request_id: str,
    status: OperationRequestStatus,
    admin_note: str = "",
    operation_name: str | None = None,
) -> dict[str, Any]:
    if status == OperationRequestStatus.PENDING:
        raise ValueError("A request can only be resolved as fulfilled or rejected")
    request = await OperationRequest.get(id=UUID(request_id)).prefetch_related(
        "requested_by", "operation"
    )
    if request.status != OperationRequestStatus.PENDING:
        raise ValueError("Operation request has already been resolved")

    if status == OperationRequestStatus.FULFILLED:
        if operation_name is None or not operation_name.strip():
            raise ValueError("operation_name is required when fulfilling a request")
        request.operation = await Operation.get(name=operation_name.strip(), is_active=True)
    elif operation_name is not None:
        raise ValueError("operation_name can only be set when fulfilling a request")

    request.status = status
    request.admin_note = admin_note.strip()
    await request.save()
    return present_operation_request(request)
