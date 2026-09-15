from types import MappingProxyType
from typing import Final

from trolley.auth.enums import Scope
from trolley.mcp.enums import SystemToolName
from trolley.mcp.types import ToolPolicy

AUTH_CONTEXT_PARAMETER: Final = "auth_context"
RESERVED_TOOL_NAMES: Final = frozenset(SystemToolName)

SYSTEM_TOOL_POLICIES: Final = MappingProxyType(
    {
        SystemToolName.CREATE_GROUP: ToolPolicy(Scope.ADMIN, ("name",)),
        SystemToolName.LIST_GROUPS: ToolPolicy(Scope.ADMIN),
        SystemToolName.UPDATE_GROUP: ToolPolicy(Scope.ADMIN, ("name",)),
        SystemToolName.DELETE_GROUP: ToolPolicy(Scope.ADMIN, ("name",)),
        SystemToolName.SET_USER_GROUPS: ToolPolicy(Scope.ADMIN, ("email",)),
        SystemToolName.LIST_GROUP_MEMBERSHIPS: ToolPolicy(Scope.ADMIN),
        SystemToolName.GRANT_GROUP_OPERATION: ToolPolicy(
            Scope.ADMIN, ("group_name", "operation_name")
        ),
        SystemToolName.REVOKE_GROUP_OPERATION: ToolPolicy(
            Scope.ADMIN, ("group_name", "operation_name")
        ),
        SystemToolName.LIST_GROUP_OPERATION_GRANTS: ToolPolicy(Scope.ADMIN),
        SystemToolName.LIST_USERS: ToolPolicy(Scope.ADMIN),
        SystemToolName.CREATE_USER: ToolPolicy(Scope.ADMIN, ("email", "name")),
        SystemToolName.INVITE_USER: ToolPolicy(Scope.ADMIN, ("email", "name", "key_name")),
        SystemToolName.UPDATE_USER_ACCESS: ToolPolicy(Scope.ADMIN, ("email",)),
        SystemToolName.LIST_API_KEYS: ToolPolicy(Scope.ADMIN, ("email",)),
        SystemToolName.CREATE_API_KEY: ToolPolicy(Scope.ADMIN, ("email", "name")),
        SystemToolName.SET_USER_ROLE: ToolPolicy(Scope.ADMIN, ("email",)),
        SystemToolName.SET_TARGET_ACCESS: ToolPolicy(Scope.ADMIN, ("name",)),
        SystemToolName.LIST_TARGET_GRANTS: ToolPolicy(Scope.ADMIN),
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
        SystemToolName.GRANT_OPERATION: ToolPolicy(Scope.ADMIN, ("email", "operation_name")),
        SystemToolName.REVOKE_OPERATION: ToolPolicy(Scope.ADMIN, ("email", "operation_name")),
        SystemToolName.LIST_OPERATION_GRANTS: ToolPolicy(Scope.ADMIN),
        SystemToolName.EXECUTE: ToolPolicy(Scope.USE, ("name",)),
    }
)
