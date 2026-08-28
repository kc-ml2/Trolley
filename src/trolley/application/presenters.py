import os
from typing import Any

from trolley.persistence.models import ApiKey, Operation, Target, User


def present_user(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "is_active": user.is_active,
    }


def present_api_key(api_key: ApiKey) -> dict[str, Any]:
    return {
        "id": str(api_key.id),
        "name": api_key.name,
        "key_prefix": api_key.key_prefix,
        "is_active": api_key.is_active,
    }


def present_target(target: Target) -> dict[str, Any]:
    return {
        "id": str(target.id),
        "name": target.name,
        "kind": target.kind,
        "configuration": target.configuration,
        "secret_env": target.secret_env,
        "secret_configured": bool(target.secret_env and os.getenv(target.secret_env)),
        "is_active": target.is_active,
    }


def present_operation(operation: Operation, *, include_definition: bool = True) -> dict[str, Any]:
    result = {
        "id": str(operation.id),
        "name": operation.name,
        "description": operation.description,
        "access": operation.access,
        "input_schema": operation.input_schema,
        "is_active": operation.is_active,
    }
    if include_definition:
        result["target"] = operation.target.name
        result["definition"] = operation.definition
    return result
