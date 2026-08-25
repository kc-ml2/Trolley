from mcp.server import MCPServer

from pantry.domain.accounts import AccountKind, AccountRole
from pantry.management import accounts


def register_account_tools(server: MCPServer) -> None:
    @server.tool(description="List Pantry human and trolley accounts")
    async def list_accounts() -> list[dict[str, str | bool | None]]:
        return await accounts.list_accounts()

    @server.tool(description="Create a human account; use create_trolley for Trolleys")
    async def create_account(
        kind: AccountKind,
        email: str | None = None,
        name: str | None = None,
        role: AccountRole = AccountRole.USER,
    ) -> dict[str, str | bool | None]:
        return await accounts.create_account(kind, email=email, name=name, role=role)

    @server.tool(description="Update an account or its active state")
    async def update_account(
        account_id: str,
        email: str | None = None,
        name: str | None = None,
        role: AccountRole | None = None,
        is_active: bool | None = None,
    ) -> dict[str, str | bool | None]:
        return await accounts.update_account(
            account_id,
            email=email,
            name=name,
            role=role,
            is_active=is_active,
        )
