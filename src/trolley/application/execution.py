import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from jsonschema import validate

from trolley.application.access import can_access_operation
from trolley.application.pagination import next_page, resolve_page
from trolley.auth.context import AuthContext
from trolley.connectors import database
from trolley.domain.operations import ExecutionStatus
from trolley.persistence.models import Execution, ExecutionPage, Operation
from trolley.serialization import json_value
from trolley.targets import get_targets

logger = logging.getLogger(__name__)


async def execute_operation(
    name: str,
    arguments: dict[str, Any] | None,
    context: AuthContext,
    *,
    page_size: int | None = None,
    cursor: str | None = None,
) -> dict:
    operation = await Operation.get(name=name).prefetch_related("target")
    target = operation.target
    if not operation.is_active or not target.is_active:
        raise ValueError("Operation or target is inactive")
    if not await can_access_operation(context, operation):
        raise PermissionError("Operation access denied")
    definition = get_targets().get(target.name)
    if definition is None or definition.kind != target.kind:
        raise ValueError("Operation target is not configured")

    arguments = arguments or {}
    validate(instance=arguments, schema=operation.input_schema)
    paginated = operation.definition.get("pagination") is not None
    if not paginated and (page_size is not None or cursor is not None):
        raise ValueError("This operation does not support pagination")
    page_options = {}
    if paginated:
        offset, page_size, fingerprint, expires_at = await resolve_page(
            operation,
            context,
            arguments,
            page_size,
            cursor,
            int(definition.configuration.get("max_rows", 1000)),
        )
        page_options = {"offset": offset, "page_size": page_size}
    execution = await Execution.create(
        operation=operation,
        arguments=arguments,
        status=ExecutionStatus.RUNNING,
        requested_by=context.user_id,
        api_key_id=context.api_key_id,
    )
    response = None
    try:
        if paginated:
            await ExecutionPage.create(
                execution=execution,
                offset=offset,
                page_size=page_size,
                input_cursor=cursor,
                query_fingerprint=fingerprint,
            )
        result = await database.execute(
            definition.configuration, operation.definition, arguments, **page_options
        )
        execution.status = ExecutionStatus.SUCCEEDED
        result = json_value(result)
        if operation.definition.get("fetch", True):
            result.setdefault("has_more", False)
            result["next_cursor"] = None
            if paginated and result["has_more"]:
                result["next_cursor"] = await next_page(
                    operation,
                    context,
                    offset + len(result["rows"]),
                    page_size,
                    fingerprint,
                    expires_at,
                )
        execution.result = result
        response = {
            "execution_id": str(execution.id),
            "status": ExecutionStatus.SUCCEEDED,
            "result": result,
        }
        return response
    except BaseException as error:
        execution.status = ExecutionStatus.FAILED
        execution.result = None
        execution.error = (
            "Execution cancelled; database outcome may be unknown"
            if isinstance(error, asyncio.CancelledError)
            else str(error)
        )
        raise
    finally:
        execution.finished_at = datetime.now(UTC)
        try:
            await asyncio.shield(execution.save())
        except Exception:
            # A completed database write must not appear failed just because the
            # independent catalog is unavailable: retrying could execute it twice.
            logger.exception("Could not finalize execution audit record %s", execution.id)
            if response is not None:
                response["audit_warning"] = (
                    "Query succeeded but audit finalization failed; do not retry the query."
                )
