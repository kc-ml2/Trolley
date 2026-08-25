from mcp.server import MCPServer

from pantry.management import resources


def register_resource_tools(server: MCPServer) -> None:
    @server.tool(description="List Resource Groups")
    async def list_resource_groups() -> list[dict]:
        return await resources.list_resource_groups()

    @server.tool(description="Create a Resource Group managed by a Trolley")
    async def create_resource_group(
        trolley_name: str,
        name: str,
        allocation_mode: str,
        configuration: dict | None = None,
        attributes: dict | None = None,
    ) -> dict:
        return await resources.create_resource_group(
            trolley_name,
            name,
            allocation_mode,
            configuration=configuration,
            attributes=attributes,
        )

    @server.tool(description="Update, enable, or disable a Resource Group")
    async def update_resource_group(
        name: str,
        allocation_mode: str | None = None,
        configuration: dict | None = None,
        attributes: dict | None = None,
        is_active: bool | None = None,
    ) -> dict:
        return await resources.update_resource_group(
            name,
            allocation_mode=allocation_mode,
            configuration=configuration,
            attributes=attributes,
            is_active=is_active,
        )

    @server.tool(description="List Resources, optionally within one Resource Group")
    async def list_resources(resource_group: str | None = None) -> list[dict]:
        return await resources.list_resources(resource_group)

    @server.tool(description="Create a Resource in a Resource Group")
    async def create_resource(
        resource_group: str,
        name: str,
        kind: str,
        attributes: dict | None = None,
    ) -> dict:
        return await resources.create_resource(
            resource_group,
            name,
            kind,
            attributes=attributes,
        )

    @server.tool(description="Update, enable, or disable a Resource")
    async def update_resource(
        resource_group: str,
        name: str,
        kind: str | None = None,
        attributes: dict | None = None,
        is_active: bool | None = None,
    ) -> dict:
        return await resources.update_resource(
            resource_group,
            name,
            kind=kind,
            attributes=attributes,
            is_active=is_active,
        )
