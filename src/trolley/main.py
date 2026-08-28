from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from tortoise.contrib.fastapi import RegisterTortoise

from trolley.application.admins import ensure_admin_users
from trolley.config import Settings, get_settings, validate_runtime_settings
from trolley.mcp.server import create_mcp_app
from trolley.persistence.database import tortoise_config


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = validate_runtime_settings(settings or get_settings())
    mcp_app = create_mcp_app(app_settings.public_base_url, app_settings.admin_emails)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with RegisterTortoise(
            app=app,
            config=tortoise_config(app_settings),
            generate_schemas=True,
        ):
            await ensure_admin_users(app_settings.admin_emails)
            await mcp_app.state.mcp_server.registry.load()
            async with mcp_app.router.lifespan_context(mcp_app):
                yield

    app = FastAPI(title="Trolley", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.mount("/mcp", mcp_app)
    return app


def app_factory() -> FastAPI:
    return create_app()
