import pytest
from fastapi.testclient import TestClient
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.mcpserver.exceptions import ToolError

from trolley.auth.api_keys import create_api_key
from trolley.config import Settings
from trolley.main import create_app
from trolley.mcp.constants import SYSTEM_TOOL_POLICIES
from trolley.mcp.token_verifier import TrolleyTokenVerifier
from trolley.persistence.models import User


def test_capabilities_follow_authenticated_discovery(tmp_path):
    settings = Settings(
        database_url=f"sqlite://{tmp_path}/test.db",
        admin_emails=frozenset({"root@example.com"}),
    )
    app = create_app(settings)
    with TestClient(app) as client:

        async def scenario():
            server = app.routes[-1].app.state.mcp_server
            tool = server._tool_manager.get_tool("get_my_capabilities")
            with pytest.raises(ToolError, match="Authentication required"):
                await tool.fn()
            member = await User.create(email="member@example.com", name="Member")
            root = await User.get(email="root@example.com")
            for user in (member, root):
                _, secret = await create_api_key(user, "test")
                token = await TrolleyTokenVerifier(settings.admin_emails).verify_token(secret)
                ctx = auth_context_var.set(AuthenticatedUser(token))
                try:
                    result = await tool.fn()
                    visible = await server.list_tools()
                    assert result["role"] == user.role
                    assert set(result["system_tools"]) == {
                        t.name for t in visible if t.name in SYSTEM_TOOL_POLICIES
                    }
                    assert "get_my_capabilities" in result["system_tools"]
                    assert "not system tools" in result["operations_note"]
                    if user == root:
                        assert "create_operation" in result["system_tools"]
                        assert any("list_targets" in s for s in result["next_steps"])
                        assert not any("request_operation" in s for s in result["next_steps"])
                    else:
                        assert "create_operation" not in result["system_tools"]
                        assert any("request_operation" in s for s in result["next_steps"])
                finally:
                    auth_context_var.reset(ctx)

        client.portal.call(scenario)
