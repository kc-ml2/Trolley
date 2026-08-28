import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any

from mcp.server import MCPServer
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver.exceptions import ToolError
from starlette.applications import Starlette

from trolley.application import grants, operations, targets, users
from trolley.application.access import accessible_operation_names
from trolley.application.execution import execute_operation
from trolley.auth.context import AuthContext
from trolley.domain.operations import OperationAccess
from trolley.domain.targets import TargetKind
from trolley.domain.users import UserOperationAccess, UserRole
from trolley.mcp.constants import AUTH_CONTEXT_PARAMETER, SYSTEM_TOOL_POLICIES
from trolley.mcp.enums import SystemToolName
from trolley.mcp.pipeline import current_tool_context, validate_tool
from trolley.mcp.registry import DynamicToolRegistry
from trolley.mcp.token_verifier import TrolleyTokenVerifier


class TrolleyMCPServer(MCPServer):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.registry = DynamicToolRegistry(self)

    def system_tool(
        self,
        name: SystemToolName,
        *,
        description: str,
    ) -> Callable:
        def decorator(fn: Callable) -> Callable:
            signature = inspect.signature(fn)
            inject_context = AUTH_CONTEXT_PARAMETER in signature.parameters
            public_parameters = [
                parameter
                for parameter_name, parameter in signature.parameters.items()
                if parameter_name != AUTH_CONTEXT_PARAMETER
            ]

            @wraps(fn)
            async def guarded(**arguments: Any) -> Any:
                try:
                    context = validate_tool(name, arguments)
                except (PermissionError, ValueError) as error:
                    raise ToolError(str(error)) from error
                if inject_context:
                    arguments[AUTH_CONTEXT_PARAMETER] = context
                try:
                    return await fn(**arguments)
                except (PermissionError, ValueError) as error:
                    raise ToolError(str(error)) from error

            guarded.__signature__ = signature.replace(parameters=public_parameters)
            self.add_tool(guarded, name=name, description=description)
            return fn

        return decorator

    async def list_tools(self) -> list:
        tools = await super().list_tools()
        auth = auth_context_var.get()
        if auth is None:
            return tools

        accessible_names = await accessible_operation_names(current_tool_context())
        visible = []
        for tool in tools:
            try:
                policy = SYSTEM_TOOL_POLICIES[SystemToolName(tool.name)]
            except ValueError:
                if tool.name not in accessible_names:
                    continue
            else:
                if policy.scope not in auth.scopes:
                    continue
            visible.append(tool)
        return visible


def create_mcp_server(
    public_base_url: str = "http://localhost:8000",
    admin_emails: frozenset[str] = frozenset(),
) -> TrolleyMCPServer:
    base_url = public_base_url.rstrip("/")
    server = TrolleyMCPServer(
        name="trolley",
        title="Trolley",
        description="Execute registered PostgreSQL and HTTP operations",
        version="0.1.0",
        token_verifier=TrolleyTokenVerifier(admin_emails),
        auth=AuthSettings(
            issuer_url=base_url,
            resource_server_url=f"{base_url}/mcp",
            required_scopes=[],
        ),
    )

    @server.system_tool(SystemToolName.LIST_USERS, description="List users (admin)")
    async def list_users() -> list[dict]:
        return await users.list_users()

    @server.system_tool(SystemToolName.CREATE_USER, description="Create a user (admin)")
    async def create_user(email: str, name: str, role: UserRole = UserRole.USER) -> dict:
        return await users.create_user(email, name, role, admin_emails=admin_emails)

    @server.system_tool(
        SystemToolName.UPDATE_USER_ACCESS,
        description="Set whether a user sees public or only assigned operations (admin)",
    )
    async def update_user_access(
        email: str,
        operation_access: UserOperationAccess,
    ) -> dict:
        return await users.update_user_access(email, operation_access)

    @server.system_tool(SystemToolName.LIST_API_KEYS, description="List a user's API keys (admin)")
    async def list_api_keys(email: str) -> list[dict]:
        return await users.list_api_keys(email)

    @server.system_tool(
        SystemToolName.CREATE_API_KEY,
        description="Issue a Bearer API key; secret is returned once (admin)",
    )
    async def create_api_key(email: str, name: str) -> dict:
        return await users.issue_api_key(email, name)

    @server.system_tool(SystemToolName.LIST_TARGETS, description="List targets (admin)")
    async def list_targets() -> list[dict]:
        return await targets.list_targets()

    @server.system_tool(
        SystemToolName.CREATE_TARGET,
        description="Register a PostgreSQL or HTTP target (admin)",
    )
    async def create_target(
        name: str,
        kind: TargetKind,
        configuration: dict,
        secret_env: str | None = None,
    ) -> dict:
        return await targets.create_target(name, kind, configuration, secret_env)

    @server.system_tool(
        SystemToolName.TEST_TARGET_CONNECTION,
        description="Test connectivity to a registered target (admin)",
    )
    async def test_target_connection(name: str) -> dict:
        return await targets.test_target_connection(name)

    @server.system_tool(
        SystemToolName.LIST_OPERATIONS,
        description="List operations visible to the current user",
    )
    async def list_operations(*, auth_context: AuthContext) -> list[dict]:
        return await operations.list_operations(auth_context)

    @server.system_tool(
        SystemToolName.CREATE_OPERATION,
        description="Register and immediately expose a dynamic operation (admin)",
    )
    async def create_operation(
        name: str,
        target_name: str,
        definition: dict,
        description: str = "",
        access: OperationAccess = OperationAccess.USER,
        input_schema: dict | None = None,
    ) -> dict:
        result = await operations.create_operation(
            name, target_name, definition, description, access, input_schema
        )
        await server.registry.reload(name)
        return result

    @server.system_tool(
        SystemToolName.UPDATE_OPERATION,
        description="Update and immediately reload a dynamic operation (admin)",
    )
    async def update_operation(
        name: str,
        description: str | None = None,
        access: OperationAccess | None = None,
        input_schema: dict | None = None,
        definition: dict | None = None,
    ) -> dict:
        result = await operations.update_operation(
            name,
            description=description,
            access=access,
            input_schema=input_schema,
            definition=definition,
        )
        await server.registry.reload(name)
        return result

    @server.system_tool(
        SystemToolName.DISABLE_OPERATION,
        description="Disable and remove a dynamic operation (admin)",
    )
    async def disable_operation(name: str) -> dict:
        result = await operations.disable_operation(name)
        await server.registry.reload(name)
        return result

    @server.system_tool(
        SystemToolName.GRANT_OPERATION,
        description="Grant a non-admin operation to a user (admin)",
    )
    async def grant_operation(email: str, operation_name: str) -> dict:
        return await grants.grant_operation(email, operation_name)

    @server.system_tool(
        SystemToolName.REVOKE_OPERATION,
        description="Revoke an operation from a user (admin)",
    )
    async def revoke_operation(email: str, operation_name: str) -> dict:
        return await grants.revoke_operation(email, operation_name)

    @server.system_tool(
        SystemToolName.LIST_OPERATION_GRANTS,
        description="List operation grants, optionally filtered (admin)",
    )
    async def list_operation_grants(
        operation_name: str | None = None,
        email: str | None = None,
    ) -> list[dict]:
        return await grants.list_operation_grants(operation_name, email)

    @server.system_tool(
        SystemToolName.RELOAD_TOOLS,
        description="Reload all dynamic operations from the database (admin)",
    )
    async def reload_tools() -> dict[str, int]:
        return {"loaded": await server.registry.load()}

    @server.system_tool(
        SystemToolName.EXECUTE,
        description="Execute an operation visible to the current user",
    )
    async def execute(
        name: str,
        arguments: dict | None = None,
        *,
        auth_context: AuthContext,
    ) -> dict:
        return await execute_operation(name, arguments, auth_context)

    return server


def create_mcp_app(
    public_base_url: str = "http://localhost:8000",
    admin_emails: frozenset[str] = frozenset(),
) -> Starlette:
    server = create_mcp_server(public_base_url, admin_emails)
    app = server.streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
        host="0.0.0.0",
    )
    app.state.mcp_server = server
    return app
