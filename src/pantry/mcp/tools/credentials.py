from mcp.server import MCPServer

from pantry.management import credentials


def register_credential_tools(server: MCPServer) -> None:
    @server.tool(description="List provider credential references without exposing secrets")
    async def list_credentials() -> list[dict[str, str | bool]]:
        return await credentials.list_credentials()

    @server.tool(description="Register a provider credential by environment variable name")
    async def create_credential(name: str, secret_env: str) -> dict[str, str | bool]:
        return await credentials.create_credential(name, secret_env)

    @server.tool(description="Update or enable/disable a provider credential reference")
    async def update_credential(
        name: str,
        secret_env: str | None = None,
        is_active: bool | None = None,
    ) -> dict[str, str | bool]:
        return await credentials.update_credential(
            name,
            secret_env=secret_env,
            is_active=is_active,
        )
