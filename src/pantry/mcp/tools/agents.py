from mcp.server import MCPServer

from pantry.management import agents


def register_agent_tools(server: MCPServer) -> None:
    @server.tool(description="List Pantry Agent definitions")
    async def list_agents() -> list[dict]:
        return await agents.list_agents()

    @server.tool(description="Create an Agent for an opaque allocation mode")
    async def create_agent(
        name: str,
        allocation_mode: str,
        model_alias: str | None = None,
        configuration: dict | None = None,
    ) -> dict:
        return await agents.create_agent(
            name,
            allocation_mode,
            model_alias=model_alias,
            configuration=configuration,
        )

    @server.tool(description="Update, enable, or disable an Agent")
    async def update_agent(
        name: str,
        allocation_mode: str | None = None,
        model_alias: str | None = None,
        clear_model: bool = False,
        configuration: dict | None = None,
        is_active: bool | None = None,
    ) -> dict:
        return await agents.update_agent(
            name,
            allocation_mode=allocation_mode,
            model_alias=model_alias,
            clear_model=clear_model,
            configuration=configuration,
            is_active=is_active,
        )
