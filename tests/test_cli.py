from tortoise import Tortoise

from trolley.cli import issue_admin_key
from trolley.config import Settings
from trolley.mcp.token_verifier import TrolleyTokenVerifier
from trolley.persistence.database import tortoise_config


def test_cli_issues_key_for_existing_admin(tmp_path) -> None:
    settings = Settings(
        database_url=f"sqlite://{tmp_path}/test.db",
    )

    import asyncio
    from argparse import Namespace

    from trolley.cli import manage_local

    asyncio.run(
        manage_local(
            settings, Namespace(action="create-user", email="admin@example.com", role="admin")
        )
    )
    secret = asyncio.run(issue_admin_key(settings, "Admin@Example.com", "local"))

    async def verify() -> None:
        await Tortoise.init(config=tortoise_config(settings))
        try:
            token = await TrolleyTokenVerifier().verify_token(secret)
            assert token is not None
            assert "trolley:admin" in token.scopes
        finally:
            await Tortoise.close_connections()

    asyncio.run(verify())
