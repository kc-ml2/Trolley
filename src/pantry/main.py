from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from tortoise.contrib.fastapi import RegisterTortoise

from pantry.api.health import router as health_router
from pantry.api.trolleys import router as trolley_router
from pantry.config import Settings, get_settings
from pantry.database import tortoise_config
from pantry.management.bootstrap import bootstrap_admin
from pantry.mcp.server import create_mcp_app


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    mcp_app = create_mcp_app(app_settings.public_base_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = app_settings
        async with RegisterTortoise(
            app=app,
            config=tortoise_config(app_settings),
            generate_schemas=True,
        ):
            await bootstrap_admin(app_settings)
            async with mcp_app.router.lifespan_context(mcp_app):
                yield

    app = FastAPI(
        title="Pantry",
        version="0.1.0",
        description="Trolley control plane",
        lifespan=lifespan,
    )
    app.include_router(health_router)
    app.include_router(trolley_router)
    app.mount("/mcp", mcp_app)
    return app


app = create_app()
