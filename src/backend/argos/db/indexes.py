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

    # ─── watch_queries (Build 1.1) ───────────────────────────────────────────
    created[col.WATCH_QUERIES] = await db[col.WATCH_QUERIES].create_indexes([
        IndexModel(
            [("workspace_id", ASCENDING), ("query", ASCENDING)],
            name="workspace_query_unique",
            unique=True,
        ),
        IndexModel(
            [("workspace_id", ASCENDING), ("activa", ASCENDING)],
            name="workspace_activa",
        ),
        IndexModel(
            [("workspace_id", ASCENDING), ("source", ASCENDING)],
            name="workspace_source",
        ),
    ])

    # ─── keywords (Build 1.3 · Trends agent) ─────────────────────────────────
    created[col.KEYWORDS] = await db[col.KEYWORDS].create_indexes([
        IndexModel(
            [("workspace_id", ASCENDING), ("keyword", ASCENDING)],
            name="workspace_keyword_unique",
            unique=True,
        ),
        IndexModel(
            [("workspace_id", ASCENDING), ("spike_detected", ASCENDING)],
            name="workspace_spike",
        ),
        IndexModel(
            [("workspace_id", ASCENDING), ("updated_at", DESCENDING)],
            name="workspace_updated_desc",
        ),
    ])

    # ─── ads_library (Build 2.1 · Competitors Meta Ad Library) ───────────────
    created[col.ADS_LIBRARY] = await db[col.ADS_LIBRARY].create_indexes([
        IndexModel(
            [("workspace_id", ASCENDING), ("plataforma", ASCENDING), ("ad_id_externo", ASCENDING)],
            name="workspace_plataforma_ad_unique",
            unique=True,
        ),
        IndexModel(
            [("workspace_id", ASCENDING), ("anunciante", ASCENDING)],
            name="workspace_anunciante",
        ),
        IndexModel(
            [("workspace_id", ASCENDING), ("activo", ASCENDING)],
            name="workspace_activo",
        ),
        IndexModel(
            [("workspace_id", ASCENDING), ("fecha_inicio", DESCENDING)],
            name="workspace_fecha_inicio_desc",
        ),
    ])

    # ─── social_accounts (Build 2.3 · Social Listening) ──────────────────────
    created[col.SOCIAL_ACCOUNTS] = await db[col.SOCIAL_ACCOUNTS].create_indexes([
        IndexModel(
            [("workspace_id", ASCENDING), ("plataforma", ASCENDING), ("username", ASCENDING)],
            name="workspace_plataforma_username_unique",
            unique=True,
        ),
        IndexModel(
            [("workspace_id", ASCENDING), ("relevancia_score", DESCENDING)],
            name="workspace_relevancia_desc",
        ),
        IndexModel(
            [("workspace_id", ASCENDING), ("seguidores", DESCENDING)],
            name="workspace_seguidores_desc",
        ),
    ])

    # ─── social_posts (Build 2.3) ────────────────────────────────────────────
    created[col.SOCIAL_POSTS] = await db[col.SOCIAL_POSTS].create_indexes([
        IndexModel(
            [("workspace_id", ASCENDING), ("post_external_id", ASCENDING)],
            name="workspace_post_external_unique",
            unique=True,
        ),
        IndexModel(
            [("workspace_id", ASCENDING), ("vistas", DESCENDING)],
            name="workspace_vistas_desc",
        ),
        IndexModel(
            [("workspace_id", ASCENDING), ("fecha_publicacion", DESCENDING)],
            name="workspace_fecha_publicacion_desc",
        ),
    ])

    # ─── briefings (Build 3.1 · Morning Briefing) ────────────────────────────
    created[col.BRIEFINGS] = await db[col.BRIEFINGS].create_indexes([
        IndexModel(
            [("workspace_id", ASCENDING), ("fecha", ASCENDING)],
            name="workspace_fecha_unique",
            unique=True,
        ),
        IndexModel(
            [("workspace_id", ASCENDING), ("created_at", DESCENDING)],
            name="workspace_created_desc",
        ),
    ])

    # ─── recommendations (Build 3.3 · Impact tracking) ───────────────────────
    created[col.RECOMMENDATIONS] = await db[col.RECOMMENDATIONS].create_indexes([
        IndexModel(
            [("workspace_id", ASCENDING), ("status", ASCENDING), ("priority_score", DESCENDING)],
            name="workspace_status_priority",
        ),
        IndexModel(
            [("workspace_id", ASCENDING), ("created_at", DESCENDING)],
            name="workspace_created_desc",
        ),
        IndexModel(
            [("workspace_id", ASCENDING), ("briefing_id", ASCENDING), ("accion_index", ASCENDING)],
            name="workspace_briefing_accion_unique",
            unique=True,
            partialFilterExpression={"briefing_id": {"$exists": True}},
        ),
        IndexModel(
            [("workspace_id", ASCENDING), ("executed_at", ASCENDING)],
            name="workspace_executed",
            partialFilterExpression={"executed_at": {"$exists": True}},
        ),
    ])

    # ─── sismo_inventory (Build 4.1 · SISMO V2 read-only) ────────────────────
    created[col.SISMO_INVENTORY] = await db[col.SISMO_INVENTORY].create_indexes([
        IndexModel(
            [("workspace_id", ASCENDING), ("sku", ASCENDING), ("fecha_sync_date", ASCENDING)],
            name="workspace_sku_fecha_unique",
            unique=True,
        ),
        IndexModel(
            [("workspace_id", ASCENDING), ("fecha_sync", DESCENDING)],
            name="workspace_fecha_sync_desc",
        ),
        IndexModel(
            [("workspace_id", ASCENDING), ("is_slow_mover", ASCENDING), ("dias_inventario", DESCENDING)],
            name="workspace_slow_movers",
        ),
    ])

    # ─── sismo_sales_daily (Build 4.2 · ventas diarias por SKU) ──────────────
    created[col.SISMO_SALES_DAILY] = await db[col.SISMO_SALES_DAILY].create_indexes([
        IndexModel(
            [("workspace_id", ASCENDING), ("date", ASCENDING), ("sku", ASCENDING)],
            name="workspace_date_sku_unique",
            unique=True,
        ),
        IndexModel(
            [("workspace_id", ASCENDING), ("date", DESCENDING)],
            name="workspace_date_desc",
        ),
        IndexModel(
            [("workspace_id", ASCENDING), ("sku", ASCENDING), ("date", DESCENDING)],
            name="workspace_sku_date_desc",
        ),
    ])

    total = sum(len(v) for v in created.values())
    logger.info("indexes_ensured", extra={"collections": list(created.keys()), "total_indexes": total})
    return created
