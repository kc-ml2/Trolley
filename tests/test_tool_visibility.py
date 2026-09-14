import pytest
from fastapi.testclient import TestClient
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.mcpserver.exceptions import ToolError

from trolley.application import grants, groups, operations, users
from trolley.auth.api_keys import create_api_key
from trolley.config import Settings
from trolley.domain.operations import OperationAccess
from trolley.domain.users import UserOperationAccess
from trolley.main import create_app
from trolley.mcp.token_verifier import TrolleyTokenVerifier
from trolley.persistence.models import Target, User


def test_dynamic_tool_list_respects_user_grants(tmp_path) -> None:
    settings = Settings(
        database_url=f"sqlite://{tmp_path}/test.db",
        admin_emails=frozenset({"root@example.com"}),
    )
    app = create_app(settings)
    with TestClient(app) as client:

        async def scenario() -> None:
            user = await User.create(email="limited@example.com", name="Limited")
            _, secret = await create_api_key(user, "test")
            await Target.create(name="db", kind="postgresql")
            await operations.create_operation(
                "public_report", "db", {"data_scope": "shared", "sql": "select 1"}
            )
            await operations.create_operation(
                "private_report",
                "db",
                {"data_scope": "shared", "sql": "select 1"},
                access=OperationAccess.RESTRICTED,
            )
            await users.update_user_access(user.email, UserOperationAccess.ASSIGNED_ONLY)
            await grants.grant_operation(user.email, "private_report")

            server = app.routes[-1].app.state.mcp_server
            await server.registry.load()
            token = await TrolleyTokenVerifier(frozenset()).verify_token(secret)
            assert token is not None
            context_token = auth_context_var.set(AuthenticatedUser(token))
            try:
                names = {tool.name for tool in await server.list_tools()}
            finally:
                auth_context_var.reset(context_token)

            assert "private_report" in names
            assert "public_report" not in names
            assert "create_target" not in names
            assert "list_operations" in names
            assert "create_group" not in names
            assert "grant_group_operation" not in names

            await grants.revoke_operation(user.email, "private_report")
            await groups.create_group("finance")
            await groups.grant_group_operation("finance", "private_report")
            await groups.set_user_groups(user.email, ["finance"])
            context_token = auth_context_var.set(AuthenticatedUser(token))
            try:
                assert "private_report" in {tool.name for tool in await server.list_tools()}
                await groups.set_user_groups(user.email, [])
                assert "private_report" not in {tool.name for tool in await server.list_tools()}
                with pytest.raises(ToolError, match="Missing required scope"):
                    await server.call_tool("create_group", {"name": "forbidden"})
            finally:
                auth_context_var.reset(context_token)

        client.portal.call(scenario)
