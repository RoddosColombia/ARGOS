from __future__ import annotations

import logging

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, IndexModel

from argos.db import collections as col

logger = logging.getLogger("argos.db.indexes")


async def ensure_indexes(db: AsyncIOMotorDatabase) -> dict[str, list[str]]:
    """Crea todos los índices declarados en docs/canonicas/colecciones_mongo.md para las
    colecciones de Build 0.3. Idempotente (create_indexes es no-op si ya existen)."""

    created: dict[str, list[str]] = {}

    # ─── workspaces ──────────────────────────────────────────────────────────
    created[col.WORKSPACES] = await db[col.WORKSPACES].create_indexes([
        IndexModel([("workspace_id", ASCENDING)], name="workspace_id_unique", unique=True),
        IndexModel([("created_at", DESCENDING)], name="created_at_desc"),
    ])

    # ─── users ───────────────────────────────────────────────────────────────
    created[col.USERS] = await db[col.USERS].create_indexes([
        IndexModel(
            [("workspace_id", ASCENDING), ("email", ASCENDING)],
            name="workspace_email_unique",
            unique=True,
        ),
        IndexModel([("created_at", DESCENDING)], name="created_at_desc"),
    ])

    # ─── argos_events (ROG-A6 · append-only) ─────────────────────────────────
    created[col.ARGOS_EVENTS] = await db[col.ARGOS_EVENTS].create_indexes([
        IndexModel([("event_id", ASCENDING)], name="event_id_unique", unique=True),
        IndexModel(
            [("workspace_id", ASCENDING), ("event_type", ASCENDING), ("timestamp_utc", DESCENDING)],
            name="workspace_event_type_ts",
        ),
        IndexModel([("correlation_id", ASCENDING)], name="correlation_id"),
        IndexModel([("causation_id", ASCENDING)], name="causation_id"),
    ])

    # ─── audit_log (ROG-A12) ─────────────────────────────────────────────────
    created[col.AUDIT_LOG] = await db[col.AUDIT_LOG].create_indexes([
        IndexModel(
            [("workspace_id", ASCENDING), ("timestamp_utc", DESCENDING)],
            name="workspace_ts",
        ),
        IndexModel(
            [("workspace_id", ASCENDING), ("actor_id", ASCENDING)],
            name="workspace_actor",
        ),
        IndexModel(
            [("workspace_id", ASCENDING), ("resource_type", ASCENDING), ("resource_id", ASCENDING)],
            name="workspace_resource",
        ),
    ])

    # ─── system_health ───────────────────────────────────────────────────────
    created[col.SYSTEM_HEALTH] = await db[col.SYSTEM_HEALTH].create_indexes([
        IndexModel(
            [("component", ASCENDING), ("timestamp_utc", DESCENDING)],
            name="component_ts",
        ),
        IndexModel([("status", ASCENDING)], name="status"),
    ])

    # ─── products_catalog (Build 1.0) ────────────────────────────────────────
    created[col.PRODUCTS_CATALOG] = await db[col.PRODUCTS_CATALOG].create_indexes([
        IndexModel(
            [("workspace_id", ASCENDING), ("sku_normalizado", ASCENDING)],
            name="workspace_sku",
        ),
        IndexModel(
            [("workspace_id", ASCENDING), ("source", ASCENDING), ("source_id", ASCENDING)],
            name="workspace_source_id_unique",
            unique=True,
        ),
        IndexModel(
            [("workspace_id", ASCENDING), ("categoria", ASCENDING)],
            name="workspace_categoria",
        ),
        IndexModel(
            [("workspace_id", ASCENDING), ("updated_at", DESCENDING)],
            name="workspace_updated_desc",
        ),
    ])

    # ─── products_history (Build 1.0 · time series) ──────────────────────────
    created[col.PRODUCTS_HISTORY] = await db[col.PRODUCTS_HISTORY].create_indexes([
        IndexModel(
            [("workspace_id", ASCENDING), ("product_id", ASCENDING), ("timestamp", DESCENDING)],
            name="workspace_product_ts",
        ),
    ])

    total = sum(len(v) for v in created.values())
    logger.info("indexes_ensured", extra={"collections": list(created.keys()), "total_indexes": total})
    return created
