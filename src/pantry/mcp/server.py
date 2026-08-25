from mcp.server import MCPServer
from mcp.server.auth.settings import AuthSettings
from starlette.applications import Starlette

from pantry.mcp.auth import ADMIN_SCOPE, PantryTokenVerifier
from pantry.mcp.tools import register_tools


def create_mcp_server(public_base_url: str) -> MCPServer:
    base_url = public_base_url.rstrip("/")
    server = MCPServer(
        name="pantry-admin",
        title="Pantry Admin",
        description="Manage Pantry accounts, Trolleys, Resources, Agents, and Providers",
        version="0.1.0",
        token_verifier=PantryTokenVerifier(),
        auth=AuthSettings(
            issuer_url=base_url,
            resource_server_url=f"{base_url}/mcp",
            required_scopes=[ADMIN_SCOPE],
        ),
    )
    register_tools(server)
    return server


def create_mcp_app(public_base_url: str) -> Starlette:
    server = create_mcp_server(public_base_url)
    return server.streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
        host="0.0.0.0",
    )
