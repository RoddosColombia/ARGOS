from __future__ import annotations

import logging
from datetime import UTC, datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.config import get_settings
from argos.db import collections as col

logger = logging.getLogger("argos.db.seed")


_DEFAULT_WATCH_QUERIES: tuple[str, ...] = (
    "aceite moto",
    "pastillas freno moto",
    "filtro aire moto",
    "bujía moto",
    "cadena 428H moto",
    "llanta Pulsar 200",
    "batería moto",
    "kit arrastre TVS Raider",
    "amortiguador trasero moto",
    "espejo retrovisor universal moto",
    "repuestos TVS Raider 125",
)


async def seed_initial_data(db: AsyncIOMotorDatabase) -> dict[str, int | bool]:
    """Seed idempotente del workspace RODDOS + user CEO + watch queries.

    - Workspace: upsert completo (settings pueden evolucionar, se refrescan).
    - User CEO: INSERT-ONLY del password_hash (no lo rota silenciosamente en restarts).
      Los otros campos (roles, workspace_id, email) se actualizan si cambiaron.
    - Watch queries (Build 1.1): seed de 11 queries semilla con $setOnInsert
      para no sobrescribir cambios manuales del CEO en Mongo.
    """
    settings = get_settings()
    now = datetime.now(tz=UTC)
    result: dict[str, int | bool] = {
        "workspace_created": False,
        "user_created": False,
        "watch_queries_inserted": 0,
    }

    # ─── Workspace RODDOS ────────────────────────────────────────────────────
    workspace_id = settings.admin_workspace_id
    ws_update = await db[col.WORKSPACES].update_one(
        {"workspace_id": workspace_id},
        {
            "$set": {
                "name": "RODDOS S.A.S.",
                "verticals": ["REPUESTOS-MOTOS", "MOTOS"],
                "settings": {"timezone": "America/Bogota", "locale": "es-CO"},
            },
            "$setOnInsert": {
                "workspace_id": workspace_id,
                "created_at": now,
            },
        },
        upsert=True,
    )
    result["workspace_created"] = ws_update.upserted_id is not None

    # ─── User CEO ────────────────────────────────────────────────────────────
    if settings.admin_email and settings.admin_password_hash:
        user_update = await db[col.USERS].update_one(
            {"workspace_id": workspace_id, "email": settings.admin_email.lower()},
            {
                "$set": {
                    "roles": [settings.admin_role],
                },
                "$setOnInsert": {
                    "workspace_id": workspace_id,
                    "email": settings.admin_email.lower(),
                    "password_hash": settings.admin_password_hash,
                    "created_at": now,
                },
            },
            upsert=True,
        )
        result["user_created"] = user_update.upserted_id is not None
    else:
        logger.warning(
            "admin_seed_skipped",
            extra={"reason": "ADMIN_EMAIL o ADMIN_PASSWORD_HASH vacíos"},
        )

    # ─── Watch queries (Build 1.1) ───────────────────────────────────────
    inserted = 0
    for query_str in _DEFAULT_WATCH_QUERIES:
        wq_update = await db[col.WATCH_QUERIES].update_one(
            {"workspace_id": workspace_id, "query": query_str},
            {
                "$setOnInsert": {
                    "workspace_id": workspace_id,
                    "query": query_str,
                    "source": "all",       # CEO puede ajustar a "meli" o "fb_marketplace"
                    "activa": True,
                    "prioridad": 1,
                    "created_at": now,
                },
            },
            upsert=True,
        )
        if wq_update.upserted_id is not None:
            inserted += 1
    result["watch_queries_inserted"] = inserted

    logger.info("seed_done", extra=result)
    return result
