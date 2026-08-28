from typing import Any

from mcp.server.auth.middleware.auth_context import auth_context_var

from trolley.auth.context import AuthContext
from trolley.domain.users import UserRole
from trolley.mcp.constants import SYSTEM_TOOL_POLICIES
from trolley.mcp.enums import SystemToolName


def current_tool_context() -> AuthContext:
    auth = auth_context_var.get()
    if auth is None:
        raise PermissionError("Authentication required")

    subject = auth.access_token.subject
    if subject is None:
        raise PermissionError("Authenticated user is missing")

    role = UserRole((auth.access_token.claims or {}).get("role", UserRole.USER))
    return AuthContext(
        user_id=subject,
        api_key_id=auth.access_token.client_id,
        role=role,
    )


def validate_tool(tool_name: SystemToolName, values: dict[str, Any] | None = None) -> AuthContext:
    policy = SYSTEM_TOOL_POLICIES[tool_name]
    context = current_tool_context()
    auth = auth_context_var.get()

    if policy.scope not in auth.scopes:
        raise PermissionError(f"Missing required scope: {policy.scope}")

    values = values or {}
    for field in policy.required_text:
        value = values.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string")

    return context
