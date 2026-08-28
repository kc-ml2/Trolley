import keyword
import re
from typing import Any

from jsonschema import Draft202012Validator

from trolley.domain.targets import TargetKind
from trolley.mcp.constants import RESERVED_TOOL_NAMES
from trolley.persistence.models import Target

TOOL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
DEFAULT_INPUT_SCHEMA = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}


def validate_operation_name(name: str) -> str:
    name = name.strip()
    if not TOOL_NAME_PATTERN.fullmatch(name):
        raise ValueError("name must contain only letters, numbers, underscores, or hyphens")
    if name in RESERVED_TOOL_NAMES:
        raise ValueError(f"Operation name is reserved by a system tool: {name}")
    return name


def validate_input_schema(input_schema: dict[str, Any]) -> dict[str, Any]:
    Draft202012Validator.check_schema(input_schema)
    if input_schema.get("type") != "object":
        raise ValueError("input_schema root type must be 'object'")
    for name in input_schema.get("properties", {}):
        if not name.isidentifier() or keyword.iskeyword(name):
            raise ValueError(f"input property must be a valid identifier: {name}")
    return input_schema


def validate_definition(
    target: Target,
    definition: dict[str, Any],
    input_schema: dict[str, Any],
) -> None:
    if target.kind != TargetKind.POSTGRESQL:
        return
    parameters = definition.get("parameters", [])
    if not isinstance(parameters, list) or not all(isinstance(item, str) for item in parameters):
        raise ValueError("PostgreSQL operation parameters must be a list of names")
    if len(parameters) != len(set(parameters)):
        raise ValueError("PostgreSQL operation parameters must be unique")
    required = set(input_schema.get("required", []))
    if set(parameters) != required:
        raise ValueError("PostgreSQL parameters must match input_schema.required")
