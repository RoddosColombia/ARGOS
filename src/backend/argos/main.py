from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from argos import __version__
from argos.api.v1.alerts import router as alerts_router
from argos.api.v1.competitors import router as competitors_router
from argos.api.v1.health import router as health_router
from argos.api.v1.marketplace import router as marketplace_router
from argos.api.v1.scout import router as scout_router
from argos.api.v1.social import router as social_router
from argos.api.v1.trends import router as trends_router
from argos.auth.router import router as auth_router
from argos.auth.user_store import EnvUserStore, MongoUserStore, set_user_store
from argos.config import get_settings
from argos.db.indexes import ensure_indexes
from argos.db.mongo import close_mongo, connect_mongo, get_mongo_client
from argos.db.seed import seed_initial_data
from argos.logging_config import configure_logging
from argos.middleware.request_logging import RequestLoggingMiddleware
from argos.middleware.workspace import WorkspaceIdMiddleware
from argos.scheduler import start_scheduler, stop_scheduler

logger = logging.getLogger("argos.main")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    await connect_mongo(verify=True)
    client = get_mongo_client()

    if client is not None:
        db = client[settings.mongodb_database]
        await ensure_indexes(db)
        await seed_initial_data(db)
        set_user_store(MongoUserStore(db))
        logger.info("mongo_ready", extra={"database": settings.mongodb_database})

        if not settings.disable_scheduler:
            start_scheduler(db, env=settings.env)
        else:
            logger.info("scheduler_disabled_by_setting")
    else:
        set_user_store(EnvUserStore())
        logger.warning("mongo_not_configured_using_env_user_store")

    try:
        yield
    finally:
        stop_scheduler()
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
    app.include_router(scout_router)
    app.include_router(marketplace_router)
    app.include_router(alerts_router)
    app.include_router(trends_router)
    app.include_router(competitors_router)
    app.include_router(social_router)

    return app


app = create_app()
