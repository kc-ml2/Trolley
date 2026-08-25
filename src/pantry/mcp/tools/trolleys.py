from mcp.server import MCPServer

from pantry.management import trolleys


def register_trolley_tools(server: MCPServer) -> None:
    @server.tool(description="List registered Trolleys and their latest state")
    async def list_trolleys() -> list[dict]:
        return await trolleys.list_trolleys()

    @server.tool(description="Create a Trolley account and return its API key once")
    async def create_trolley(name: str) -> dict:
        created = await trolleys.create_trolley(name)
        return {
            "id": created.id,
            "account_id": created.account_id,
            "name": created.name,
            "api_key": created.api_key,
        }

    @server.tool(description="Enable or disable a Trolley")
    async def update_trolley(name: str, is_active: bool | None = None) -> dict:
        return await trolleys.update_trolley(name, is_active=is_active)
