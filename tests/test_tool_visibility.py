from access_helpers import allow, revoke
from fastapi.testclient import TestClient
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser

from trolley.application.operations import create_operation
from trolley.auth.api_keys import create_api_key
from trolley.config import Settings
from trolley.main import create_app
from trolley.mcp.token_verifier import TrolleyTokenVerifier
from trolley.persistence.models import Target, User


def test_tool_visibility_follows_group_access(tmp_path):
    settings = Settings(
        database_url=f"sqlite://{tmp_path}/test.db",
    )
    app = create_app(settings)
    with TestClient(app) as client:

        async def scenario():
            await Target.create(name="db", kind="postgresql")
            await create_operation("report", "db", {"data_scope": "shared", "sql": "SELECT 1"})
            user = await User.create(email="member@example.com", name="Member")
            _, key = await create_api_key(user, "test")
            token = await TrolleyTokenVerifier().verify_token(key)
            server = app.routes[-1].app.state.mcp_server
            await server.registry.load()
            ctx = auth_context_var.set(AuthenticatedUser(token))
            try:
                assert "report" not in {t.name for t in await server.list_tools()}
                await allow(user, "db")
                assert "report" in {t.name for t in await server.list_tools()}
                await revoke(user)
                assert "report" not in {t.name for t in await server.list_tools()}
            finally:
                auth_context_var.reset(ctx)

        client.portal.call(scenario)
