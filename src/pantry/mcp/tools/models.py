from mcp.server import MCPServer

from pantry.management import models


def register_model_tools(server: MCPServer) -> None:
    @server.tool(description="List all registered model aliases")
    async def list_models() -> list[dict[str, str | bool]]:
        return await models.list_models()

    @server.tool(description="Register a model alias for a provider")
    async def create_model(
        alias: str,
        upstream_model: str,
        provider_name: str,
    ) -> dict[str, str | bool]:
        return await models.create_model(alias, upstream_model, provider_name)

    @server.tool(description="Update, enable, or disable a registered model alias")
    async def update_model(
        alias: str,
        upstream_model: str | None = None,
        provider_name: str | None = None,
        is_active: bool | None = None,
    ) -> dict[str, str | bool]:
        return await models.update_model(
            alias,
            upstream_model=upstream_model,
            provider_name=provider_name,
            is_active=is_active,
        )
