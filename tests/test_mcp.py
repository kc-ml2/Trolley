import asyncio

import pytest

from trolley.mcp.registry import DynamicToolRegistry
from trolley.mcp.server import create_mcp_server


def test_mcp_has_small_tool_surface() -> None:
    server = create_mcp_server()

    async def names() -> set[str]:
        return {tool.name for tool in await server.list_tools()}

    assert isinstance(server.registry, DynamicToolRegistry)
    assert server.registry.server is server
    assert asyncio.run(names()) == {
        "list_users",
        "create_user",
        "list_api_keys",
        "create_api_key",
        "list_targets",
        "create_target",
        "test_target_connection",
        "list_operations",
        "create_operation",
        "update_operation",
        "disable_operation",
        "reload_tools",
        "execute",
    }


def test_system_tool_decorator_hides_injected_context_and_enforces_auth() -> None:
    server = create_mcp_server()

    async def schema() -> dict:
        tools = {tool.name: tool for tool in await server.list_tools()}
        assert "auth_context" not in tools["execute"].input_schema["properties"]
        return tools["create_user"].input_schema

    create_user_schema = asyncio.run(schema())
    assert set(create_user_schema["properties"]) == {"email", "name", "role"}

    with pytest.raises(Exception, match="Authentication required"):
        asyncio.run(server.call_tool("list_users", {}))
