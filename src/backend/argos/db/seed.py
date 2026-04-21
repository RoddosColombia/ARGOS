from __future__ import annotations

import logging
from datetime import UTC, datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.config import get_settings
from argos.db import collections as col

logger = logging.getLogger("argos.db.seed")


async def seed_initial_data(db: AsyncIOMotorDatabase) -> dict[str, bool]:
    """Seed idempotente del workspace RODDOS + user CEO.

    - Workspace: upsert completo (settings pueden evolucionar, se refrescan).
    - User CEO: INSERT-ONLY del password_hash (no lo rota silenciosamente en restarts).
      Los otros campos (roles, workspace_id, email) se actualizan si cambiaron.
    """
    settings = get_settings()
    now = datetime.now(tz=UTC)
    result: dict[str, bool] = {"workspace_created": False, "user_created": False}

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

    logger.info("seed_done", extra=result)
    return result
