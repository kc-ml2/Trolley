import asyncio

import pytest

from trolley.config import Settings
from trolley.mcp.registry import DynamicToolRegistry
from trolley.mcp.server import create_mcp_server


def test_mcp_has_small_tool_surface() -> None:
    server = create_mcp_server(settings=Settings())

    async def names() -> set[str]:
        return {tool.name for tool in await server.list_tools()}

    assert isinstance(server.registry, DynamicToolRegistry)
    assert server.registry.server is server
    assert asyncio.run(names()) == {
        "query_target",
        "list_targets",
        "get_target_schema",
        "get_target_notes",
        "update_target_notes",
        "list_operations",
        "get_my_capabilities",
        "get_execution",
        "create_operation",
        "update_operation",
        "disable_operation",
        "execute",
    }


def test_server_instructs_agents_to_discover_operations() -> None:
    server = create_mcp_server()

    assert "Call get_my_capabilities after connecting" in server._lowlevel_server.instructions
    assert "Use execute" in server._lowlevel_server.instructions
    assert "has_more" in server._lowlevel_server.instructions
    assert "not a database snapshot" in server._lowlevel_server.instructions


def test_system_tool_decorator_hides_injected_context_and_enforces_auth() -> None:
    server = create_mcp_server()

    async def schema() -> dict:
        tools = {tool.name: tool for tool in await server.list_tools()}
        execute_properties = tools["execute"].input_schema["properties"]
        assert "auth_context" not in execute_properties
        assert {"name", "arguments", "page_size", "cursor"} == set(execute_properties)
        return tools["create_operation"].input_schema

    create_user_schema = asyncio.run(schema())
    assert set(create_user_schema["properties"]) == {
        "name",
        "target_name",
        "definition",
        "description",
        "input_schema",
    }

    with pytest.raises(Exception, match="Authentication required"):
        asyncio.run(server.call_tool("list_operations", {}))
