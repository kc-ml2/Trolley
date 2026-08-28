from datetime import UTC, datetime
from typing import Any

from jsonschema import validate

from trolley.application.access import can_access_operation
from trolley.auth.context import AuthContext
from trolley.connectors import database, http
from trolley.domain.operations import ExecutionStatus
from trolley.domain.targets import TargetKind
from trolley.persistence.models import Execution, Operation


async def execute_operation(
    name: str,
    arguments: dict[str, Any] | None,
    context: AuthContext,
) -> dict:
    operation = await Operation.get(name=name).prefetch_related("target")
    target = operation.target
    if not operation.is_active or not target.is_active:
        raise ValueError("Operation or target is inactive")
    if not await can_access_operation(context, operation):
        raise PermissionError("Operation access denied")

    arguments = arguments or {}
    validate(instance=arguments, schema=operation.input_schema)
    execution = await Execution.create(
        operation=operation,
        arguments=arguments,
        status=ExecutionStatus.RUNNING,
        requested_by=context.user_id,
        api_key_id=context.api_key_id,
    )
    try:
        if target.kind == TargetKind.POSTGRESQL:
            result = await database.execute(
                target.configuration, operation.definition, arguments, target.secret_env
            )
        elif target.kind == TargetKind.HTTP:
            result = await http.execute(
                target.configuration, operation.definition, arguments, target.secret_env
            )
        else:
            raise ValueError(f"Unsupported target kind: {target.kind}")
        execution.status = ExecutionStatus.SUCCEEDED
        execution.result = result
        return {
            "execution_id": str(execution.id),
            "status": ExecutionStatus.SUCCEEDED,
            "result": result,
        }
    except Exception as error:
        execution.status = ExecutionStatus.FAILED
        execution.error = str(error)
        raise
    finally:
        execution.finished_at = datetime.now(UTC)
        await execution.save()
