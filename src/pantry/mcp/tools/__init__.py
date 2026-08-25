"""Admin MCP tools."""

from mcp.server import MCPServer

from pantry.mcp.tools.accounts import register_account_tools
from pantry.mcp.tools.agents import register_agent_tools
from pantry.mcp.tools.api_keys import register_api_key_tools
from pantry.mcp.tools.credentials import register_credential_tools
from pantry.mcp.tools.models import register_model_tools
from pantry.mcp.tools.providers import register_provider_tools
from pantry.mcp.tools.resources import register_resource_tools
from pantry.mcp.tools.trolleys import register_trolley_tools


def register_tools(server: MCPServer) -> None:
    register_credential_tools(server)
    register_provider_tools(server)
    register_model_tools(server)
    register_account_tools(server)
    register_api_key_tools(server)
    register_trolley_tools(server)
    register_resource_tools(server)
    register_agent_tools(server)
