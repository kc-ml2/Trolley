from fastapi.testclient import TestClient
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser

from trolley.application import grants, operations, targets, users
from trolley.auth.api_keys import create_api_key
from trolley.config import Settings
from trolley.domain.operations import OperationAccess
from trolley.domain.users import UserOperationAccess
from trolley.main import create_app
from trolley.mcp.token_verifier import TrolleyTokenVerifier
from trolley.persistence.models import User


def test_dynamic_tool_list_respects_user_grants(tmp_path) -> None:
    settings = Settings(_env_file=None, database_url=f"sqlite://{tmp_path}/test.db")
    app = create_app(settings)
    with TestClient(app) as client:

        async def scenario() -> None:
            user = await User.create(email="limited@example.com", name="Limited")
            _, secret = await create_api_key(user, "test")
            await targets.create_target("db", "postgresql", {}, "DATABASE_URL")
            await operations.create_operation("public_report", "db", {"sql": "select 1"})
            await operations.create_operation(
                "private_report",
                "db",
                {"sql": "select 1"},
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

        client.portal.call(scenario)
