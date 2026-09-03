import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any

from mcp.server import MCPServer
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver.exceptions import ToolError
from starlette.applications import Starlette

from trolley.application import grants, operation_requests, operations, targets, users
from trolley.application.access import accessible_operation_names
from trolley.application.execution import execute_operation
from trolley.auth.context import AuthContext
from trolley.config import Settings
from trolley.domain.operation_requests import OperationRequestStatus
from trolley.domain.operations import OperationAccess
from trolley.domain.users import UserOperationAccess, UserRole
from trolley.email import EmailService
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
    settings: Settings | None = None,
) -> TrolleyMCPServer:
    base_url = public_base_url.rstrip("/")
    email_service = EmailService(settings or Settings(_env_file=None))
    onboarding_url = f"{base_url}/onboarding.md"
    server = TrolleyMCPServer(
        name="trolley",
        title="Trolley",
        description="Execute registered PostgreSQL operations",
        instructions=(
            "Trolley operations may change at runtime. Call list_operations after "
            "connecting to discover the operations currently available to you. Use "
            "execute with an operation name and arguments matching its input_schema. "
            "Call list_operations again whenever an expected operation is missing or "
            "permissions may have changed. If no operation meets the user's need, ask "
            "for confirmation before recording it with request_operation. Never include "
            "credentials or sensitive data in a request. Dynamic operation tools are "
            "conveniences; prefer list_operations and execute when the cached tool list "
            "may be stale."
        ),
        version="0.1.0",
        token_verifier=TrolleyTokenVerifier(admin_emails),
        auth=AuthSettings(
            issuer_url=base_url,
            resource_server_url=f"{base_url}/mcp",
            required_scopes=[],
        ),
    )
    server.email_service = email_service

    @server.system_tool(SystemToolName.LIST_USERS, description="List users (admin)")
    async def list_users() -> list[dict]:
        return await users.list_users()

    @server.system_tool(SystemToolName.CREATE_USER, description="Create a user (admin)")
    async def create_user(email: str, name: str, role: UserRole = UserRole.USER) -> dict:
        return await users.create_user(email, name, role, admin_emails=admin_emails)

    @server.system_tool(
        SystemToolName.INVITE_USER,
        description=(
            "Create or reuse a user and email a one-time Trolley API key (admin). "
            "Emails in TROLLEY_ADMIN_EMAILS receive the admin role."
        ),
    )
    async def invite_user(email: str, name: str, key_name: str = "initial-access") -> dict:
        return await users.invite_user(
            email,
            name,
            key_name,
            email_service,
            onboarding_url,
            admin_emails=admin_emails,
        )

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

    if settings is not None:

        @server.system_tool(SystemToolName.LIST_TARGETS, description="List targets (admin)")
        async def list_targets() -> list[dict]:
            return await targets.list_targets(settings)

        @server.system_tool(
            SystemToolName.GET_TARGET_SCHEMA,
            description="Inspect the complete live schema of a target (admin)",
        )
        async def get_target_schema(name: str) -> dict:
            return await targets.get_target_schema(settings, name)

    @server.system_tool(
        SystemToolName.LIST_OPERATIONS,
        description=(
            "Discover the operations currently available to the authenticated user. "
            "Call this after connecting and again when operations or permissions may "
            "have changed."
        ),
    )
    async def list_operations(*, auth_context: AuthContext) -> list[dict]:
        return await operations.list_operations(auth_context)

    @server.system_tool(
        SystemToolName.REQUEST_OPERATION,
        description=(
            "Record a request for a missing operation after checking list_operations "
            "and obtaining the user's confirmation. Do not include credentials or "
            "sensitive data."
        ),
    )
    async def request_operation(
        title: str,
        description: str,
        reason: str,
        *,
        auth_context: AuthContext,
    ) -> dict:
        return await operation_requests.request_operation(title, description, reason, auth_context)

    @server.system_tool(
        SystemToolName.LIST_MY_OPERATION_REQUESTS,
        description="List the authenticated user's operation requests and their status",
    )
    async def list_my_operation_requests(*, auth_context: AuthContext) -> list[dict]:
        return await operation_requests.list_my_operation_requests(auth_context)

    @server.system_tool(
        SystemToolName.LIST_OPERATION_REQUESTS,
        description="List operation requests for administrator review",
    )
    async def list_operation_requests(
        status: OperationRequestStatus | None = None,
    ) -> list[dict]:
        return await operation_requests.list_operation_requests(status)

    @server.system_tool(
        SystemToolName.RESOLVE_OPERATION_REQUEST,
        description="Mark an operation request as fulfilled or rejected (admin)",
    )
    async def resolve_operation_request(
        request_id: str,
        status: OperationRequestStatus,
        admin_note: str = "",
        operation_name: str | None = None,
    ) -> dict:
        return await operation_requests.resolve_operation_request(
            request_id, status, admin_note, operation_name
        )

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
        description=(
            "Execute an available operation by name. Use list_operations to discover "
            "the operation and construct arguments matching its input_schema."
        ),
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
    settings: Settings | None = None,
) -> Starlette:
    server = create_mcp_server(public_base_url, admin_emails, settings)
    app = server.streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
        host="0.0.0.0",
    )
    app.state.mcp_server = server
    app.state.email_service = server.email_service
    return app
