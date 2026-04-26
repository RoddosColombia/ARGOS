"""Repo de watch queries · lee desde Mongo (Build 1.1+)."""
from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.db import collections as col


async def get_active_queries(
    db: AsyncIOMotorDatabase, workspace_id: str
) -> list[dict[str, Any]]:
    """Devuelve queries activas del workspace ordenadas por prioridad desc."""
    cursor = (
        db[col.WATCH_QUERIES]
        .find({"workspace_id": workspace_id, "activa": True})
        .sort("prioridad", -1)
    )
    return await cursor.to_list(length=None)


async def list_all_queries(
    db: AsyncIOMotorDatabase, workspace_id: str
) -> list[dict[str, Any]]:
    """Devuelve TODAS las queries del workspace (activas + inactivas)."""
    cursor = db[col.WATCH_QUERIES].find({"workspace_id": workspace_id}).sort("query", 1)
    return await cursor.to_list(length=None)
