from types import MappingProxyType
from typing import Final

from trolley.auth.enums import Scope
from trolley.mcp.enums import SystemToolName
from trolley.mcp.types import ToolPolicy

AUTH_CONTEXT_PARAMETER: Final = "auth_context"
RESERVED_TOOL_NAMES: Final = frozenset(SystemToolName)

SYSTEM_TOOL_POLICIES: Final = MappingProxyType(
    {
        SystemToolName.QUERY_TARGET: ToolPolicy(Scope.QUERY, ("name", "sql")),
        SystemToolName.LIST_TARGETS: ToolPolicy(Scope.QUERY),
        SystemToolName.GET_TARGET_SCHEMA: ToolPolicy(Scope.QUERY, ("name",)),
        SystemToolName.GET_TARGET_NOTES: ToolPolicy(Scope.QUERY, ("name",)),
        SystemToolName.UPDATE_TARGET_NOTES: ToolPolicy(Scope.QUERY, ("name",)),
        SystemToolName.GET_EXECUTION: ToolPolicy(Scope.USE, ("execution_id",)),
        SystemToolName.GET_MY_CAPABILITIES: ToolPolicy(Scope.USE),
        SystemToolName.LIST_OPERATIONS: ToolPolicy(Scope.USE),
        SystemToolName.CREATE_OPERATION: ToolPolicy(Scope.ADMIN, ("name", "target_name")),
        SystemToolName.UPDATE_OPERATION: ToolPolicy(Scope.ADMIN, ("name",)),
        SystemToolName.DISABLE_OPERATION: ToolPolicy(Scope.ADMIN, ("name",)),
        SystemToolName.EXECUTE: ToolPolicy(Scope.USE, ("name",)),
    }
)
