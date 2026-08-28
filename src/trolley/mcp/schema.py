import inspect
from types import MappingProxyType
from typing import Any, Final

MISSING_ARGUMENT: Final = object()

JSON_SCHEMA_TYPES: Final = MappingProxyType(
    {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
)


def create_tool_signature(schema: dict[str, Any]) -> inspect.Signature:
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    parameters = []

    for name, definition in properties.items():
        default = (
            inspect.Parameter.empty
            if name in required
            else definition.get("default", MISSING_ARGUMENT)
        )
        parameters.append(
            inspect.Parameter(
                name,
                inspect.Parameter.KEYWORD_ONLY,
                default=default,
                annotation=JSON_SCHEMA_TYPES.get(definition.get("type"), Any),
            )
        )

    return inspect.Signature(parameters, return_annotation=dict)


def remove_missing_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    return {name: value for name, value in arguments.items() if value is not MISSING_ARGUMENT}
