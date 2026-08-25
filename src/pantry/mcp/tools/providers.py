from mcp.server import MCPServer

from pantry.management import providers


def register_provider_tools(server: MCPServer) -> None:
    @server.tool(description="List registered OpenAI-compatible providers")
    async def list_providers() -> list[dict[str, str | bool | None]]:
        return await providers.list_providers()

    @server.tool(description="Register an OpenAI-compatible provider")
    async def create_provider(
        name: str,
        base_url: str,
        credential_name: str | None = None,
    ) -> dict[str, str | bool | None]:
        return await providers.create_provider(name, base_url, credential_name)

    @server.tool(description="Update, enable, or disable a provider")
    async def update_provider(
        name: str,
        base_url: str | None = None,
        credential_name: str | None = None,
        clear_credential: bool = False,
        is_active: bool | None = None,
    ) -> dict[str, str | bool | None]:
        return await providers.update_provider(
            name,
            base_url=base_url,
            credential_name=credential_name,
            clear_credential=clear_credential,
            is_active=is_active,
        )
