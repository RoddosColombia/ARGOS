from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from argos import __version__
from argos.db.mongo import get_mongo_client

router = APIRouter(prefix="/api/v1/health", tags=["health"])
logger = logging.getLogger("argos.health")


@router.get("")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/deep")
async def health_deep() -> JSONResponse:
    mongo_status: dict[str, Any]
    client = get_mongo_client()

    if client is None:
        mongo_status = {"state": "not_configured"}
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "degraded", "version": __version__, "mongodb": mongo_status},
        )

    try:
        await asyncio.wait_for(client.admin.command("ping"), timeout=2.0)
        mongo_status = {"state": "ok"}
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ok", "version": __version__, "mongodb": mongo_status},
        )
    except TimeoutError:
        mongo_status = {"state": "timeout"}
    except Exception as exc:  # noqa: BLE001 — se reporta como payload
        logger.warning("mongo_ping_failed", extra={"error": str(exc)})
        mongo_status = {"state": "error", "detail": str(exc)[:200]}

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "degraded", "version": __version__, "mongodb": mongo_status},
    )
