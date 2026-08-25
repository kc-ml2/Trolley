from mcp.server import MCPServer

from pantry.management import api_keys


def register_api_key_tools(server: MCPServer) -> None:
    @server.tool(description="List API key metadata without exposing key secrets")
    async def list_api_keys(account_id: str | None = None) -> list[dict[str, str | bool | None]]:
        return await api_keys.list_api_keys(account_id)

    @server.tool(description="Issue an API key; the secret is returned only by this call")
    async def create_api_key(account_id: str, name: str) -> dict[str, str | bool]:
        issued = await api_keys.issue_api_key(account_id, name)
        return {
            "id": issued.id,
            "name": issued.name,
            "key_prefix": issued.key_prefix,
            "secret": issued.secret,
            "is_active": issued.is_active,
        }

    @server.tool(description="Enable or disable an API key by ID")
    async def update_api_key(api_key_id: str, is_active: bool) -> dict[str, str | bool | None]:
        return await api_keys.update_api_key(api_key_id, is_active=is_active)
