from types import MappingProxyType
from typing import Final

from trolley.auth.enums import Scope
from trolley.mcp.enums import SystemToolName
from trolley.mcp.types import ToolPolicy

AUTH_CONTEXT_PARAMETER: Final = "auth_context"
RESERVED_TOOL_NAMES: Final = frozenset(SystemToolName)

SYSTEM_TOOL_POLICIES: Final = MappingProxyType(
    {
        SystemToolName.LIST_USERS: ToolPolicy(Scope.ADMIN),
        SystemToolName.CREATE_USER: ToolPolicy(Scope.ADMIN, ("email", "name")),
        SystemToolName.UPDATE_USER_ACCESS: ToolPolicy(Scope.ADMIN, ("email",)),
        SystemToolName.LIST_API_KEYS: ToolPolicy(Scope.ADMIN, ("email",)),
        SystemToolName.CREATE_API_KEY: ToolPolicy(Scope.ADMIN, ("email", "name")),
        SystemToolName.LIST_TARGETS: ToolPolicy(Scope.ADMIN),
        SystemToolName.GET_TARGET_SCHEMA: ToolPolicy(Scope.ADMIN, ("name",)),
        SystemToolName.LIST_OPERATIONS: ToolPolicy(Scope.USE),
        SystemToolName.CREATE_OPERATION: ToolPolicy(Scope.ADMIN, ("name", "target_name")),
        SystemToolName.UPDATE_OPERATION: ToolPolicy(Scope.ADMIN, ("name",)),
        SystemToolName.DISABLE_OPERATION: ToolPolicy(Scope.ADMIN, ("name",)),
        SystemToolName.GRANT_OPERATION: ToolPolicy(Scope.ADMIN, ("email", "operation_name")),
        SystemToolName.REVOKE_OPERATION: ToolPolicy(Scope.ADMIN, ("email", "operation_name")),
        SystemToolName.LIST_OPERATION_GRANTS: ToolPolicy(Scope.ADMIN),
        SystemToolName.RELOAD_TOOLS: ToolPolicy(Scope.ADMIN),
        SystemToolName.EXECUTE: ToolPolicy(Scope.USE, ("name",)),
    }
)
