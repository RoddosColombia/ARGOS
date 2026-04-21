from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from argos import __version__
from argos.api.v1.health import router as health_router
from argos.auth.router import router as auth_router
from argos.config import get_settings
from argos.db.mongo import close_mongo, connect_mongo
from argos.logging_config import configure_logging
from argos.middleware.request_logging import RequestLoggingMiddleware
from argos.middleware.workspace import WorkspaceIdMiddleware


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await connect_mongo()
    try:
        yield
    finally:
        await close_mongo()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="ARGOS Backend",
        version=__version__,
        lifespan=lifespan,
    )

    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(WorkspaceIdMiddleware)

    app.include_router(health_router)
    app.include_router(auth_router)

    return app


app = create_app()
