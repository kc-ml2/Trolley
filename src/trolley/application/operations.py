from typing import Any

from trolley.application.presenters import present_operation
from trolley.domain.operations import OperationAccess
from trolley.domain.users import UserRole
from trolley.persistence.models import Operation, Target
from trolley.validation.operations import (
    DEFAULT_INPUT_SCHEMA,
    validate_definition,
    validate_input_schema,
    validate_operation_name,
)


async def list_operations(role: UserRole = UserRole.USER) -> list[dict[str, Any]]:
    query = Operation.filter(is_active=True)
    if role != UserRole.ADMIN:
        query = query.filter(access=OperationAccess.USER)
    operations = await query.prefetch_related("target").order_by("name")
    include_definition = role == UserRole.ADMIN
    return [
        present_operation(operation, include_definition=include_definition)
        for operation in operations
    ]


async def create_operation(
    name: str,
    target_name: str,
    definition: dict[str, Any],
    description: str = "",
    access: OperationAccess = OperationAccess.USER,
    input_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    target = await Target.get(name=target_name)
    input_schema = validate_input_schema(input_schema or DEFAULT_INPUT_SCHEMA)
    validate_definition(target, definition, input_schema)
    operation = await Operation.create(
        name=validate_operation_name(name),
        target=target,
        description=description,
        access=access,
        input_schema=input_schema,
        definition=definition,
    )
    operation.target = target
    return present_operation(operation)


async def update_operation(
    name: str,
    *,
    description: str | None = None,
    access: OperationAccess | None = None,
    input_schema: dict[str, Any] | None = None,
    definition: dict[str, Any] | None = None,
) -> dict[str, Any]:
    operation = await Operation.get(name=name).prefetch_related("target")
    if description is not None:
        operation.description = description
    if access is not None:
        operation.access = access
    next_schema = (
        validate_input_schema(input_schema) if input_schema is not None else operation.input_schema
    )
    next_definition = definition if definition is not None else operation.definition
    validate_definition(operation.target, next_definition, next_schema)
    operation.input_schema = next_schema
    operation.definition = next_definition
    operation.is_active = True
    await operation.save()
    return present_operation(operation)


async def disable_operation(name: str) -> dict[str, Any]:
    operation = await Operation.get(name=name).prefetch_related("target")
    operation.is_active = False
    await operation.save()
    return present_operation(operation)
