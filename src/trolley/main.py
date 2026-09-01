from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from tortoise.contrib.fastapi import RegisterTortoise

from trolley.application import targets
from trolley.application.admins import ensure_admin_users
from trolley.config import Settings, get_settings, validate_runtime_settings
from trolley.mcp.server import create_mcp_app
from trolley.persistence.database import tortoise_config
from trolley.targets import configure_targets


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = validate_runtime_settings(settings or get_settings())
    configure_targets(app_settings.targets_file)
    mcp_app = create_mcp_app(
        app_settings.public_base_url,
        app_settings.admin_emails,
        app_settings,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with RegisterTortoise(
            app=app,
            config=tortoise_config(app_settings),
            generate_schemas=True,
        ):
            await ensure_admin_users(app_settings.admin_emails)
            if app_settings.smtp_host:
                await mcp_app.state.email_service.check()
            await targets.sync_targets(app_settings)
            await mcp_app.state.mcp_server.registry.load()
            async with mcp_app.router.lifespan_context(mcp_app):
                yield

    app = FastAPI(title="Trolley", version="0.1.0", lifespan=lifespan)

    base_url = app_settings.public_base_url.rstrip("/")
    mcp_url = f"{base_url}/mcp/"
    onboarding_url = f"{base_url}/onboarding.md"

    @app.get("/health")
    async def health() -> dict[str, str]:
        if not app_settings.smtp_host:
            email_status = "disabled"
        elif mcp_app.state.email_service.available:
            email_status = "ready"
        else:
            email_status = "unavailable"
        return {"status": "ok", "email": email_status}

    @app.get("/.well-known/trolley")
    async def trolley_discovery() -> dict:
        return {
            "name": "Trolley",
            "mcp_url": mcp_url,
            "onboarding_url": onboarding_url,
            "authentication": {
                "type": "bearer",
                "secret_input": "user_managed",
                "recommended_environment_variable": "TROLLEY_API_KEY",
            },
        }

    @app.get("/onboarding.md", response_class=PlainTextResponse)
    async def onboarding() -> PlainTextResponse:
        document = f"""# Connect to Trolley

MCP endpoint: `{mcp_url}`

Trolley requires a Bearer API key. If the user does not have one, ask them to
request one from their Trolley administrator.

## Security instructions

- Never ask the user to paste an API key into the conversation.
- Never read, echo, store, or validate the raw key yourself.
- Prepare the MCP configuration with a secret placeholder.
- Ask the user to enter the key directly in the MCP client's secret settings or
  in a local `TROLLEY_API_KEY` environment variable.
- After the user confirms that the key is configured, reconnect to Trolley.

## Using Trolley

After connecting, call `list_operations` to discover the operations currently
available to the authenticated user. Choose an operation, construct arguments
that match its `input_schema`, and call `execute`. Call `list_operations` again
when an expected operation is missing or permissions may have changed. Dynamic
operation tools are conveniences and a client's cached Tool list may be stale.
If no available operation meets the user's need, ask for confirmation before
calling `request_operation`. Never put credentials or sensitive data in a
request. Use `list_my_operation_requests` to check its status later.

Example configuration (adapt it to the MCP client):

```json
{{
  "mcpServers": {{
    "trolley": {{
      "url": "{mcp_url}",
      "headers": {{
        "Authorization": "Bearer ${{TROLLEY_API_KEY}}"
      }}
    }}
  }}
}}
```

A `401` response means the key is missing, invalid, or inactive. A permission
error after connecting means the authenticated user does not have access to the
requested tool or operation; ask a Trolley administrator for access.
"""
        return PlainTextResponse(document, media_type="text/markdown")

    app.mount("/mcp", mcp_app)
    return app


def app_factory() -> FastAPI:
    return create_app()
