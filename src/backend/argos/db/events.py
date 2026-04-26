"""Event publisher para el bus argos_events (ROG-A6 · append-only, inmutable).

Ver docs/canonicas/eventos.md para el schema base y el catálogo de event_types.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from ulid import ULID

from argos.db import collections as col

logger = logging.getLogger("argos.db.events")

EVENT_SCHEMA_VERSION = "1.0"


class EventValidationError(ValueError):
    """Raised cuando un evento no cumple el schema mínimo."""


def _validate(event_type: str, workspace_id: str, producer: str, payload: dict[str, Any]) -> None:
    if not event_type or "." not in event_type:
        raise EventValidationError("event_type debe usar dot.notation (ej: score.evaluated)")
    if not workspace_id:
        raise EventValidationError("workspace_id es obligatorio (ROG-A3)")
    if not producer:
        raise EventValidationError("producer es obligatorio")
    if not isinstance(payload, dict):
        raise EventValidationError("payload debe ser dict")


async def publish_event(
    db: AsyncIOMotorDatabase,
    *,
    event_type: str,
    workspace_id: str,
    producer: str,
    payload: dict[str, Any],
    correlation_id: str | None = None,
    causation_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    version: str = EVENT_SCHEMA_VERSION,
) -> dict[str, Any]:
    """Emite un evento al bus. Devuelve el documento persistido (con event_id ULID).

    Idempotencia: si dos emisiones usan el mismo event_id, la segunda fallará
    por el índice unique (event_id). Es responsabilidad del caller usar ULIDs
    frescos · en flujos con retry se debe cachear el event_id generado.
    """
    _validate(event_type, workspace_id, producer, payload)

    event_id = f"evt_{ULID()}"
    doc: dict[str, Any] = {
        "event_id": event_id,
        "event_type": event_type,
        "version": version,
        "workspace_id": workspace_id,
        "timestamp_utc": datetime.now(tz=UTC),
        "producer": producer,
        "correlation_id": correlation_id,
        "causation_id": causation_id,
        "payload": payload,
        "metadata": metadata or {},
    }
    await db[col.ARGOS_EVENTS].insert_one(doc)
    logger.info(
        "event_published",
        extra={"event_id": event_id, "event_type": event_type, "workspace_id": workspace_id},
    )
    return doc


# ─── Helpers específicos por dominio (Build 1.0) ─────────────────────────


async def publish_marketplace_product_detected(
    db: AsyncIOMotorDatabase,
    *,
    workspace_id: str,
    sku_normalizado: str,
    source: str,
    source_id: str,
    nombre: str,
    categoria: str,
    precio_actual: float,
    created: bool,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    return await publish_event(
        db,
        event_type="marketplace.product.detected",
        workspace_id=workspace_id,
        producer="marketplace_agent",
        payload={
            "sku_normalizado": sku_normalizado,
            "source": source,
            "source_id": source_id,
            "nombre": nombre,
            "categoria": categoria,
            "precio_actual": precio_actual,
            "created": created,
        },
        correlation_id=correlation_id,
    )


async def publish_scout_product_discarded(
    db: AsyncIOMotorDatabase,
    *,
    workspace_id: str,
    source: str,
    source_id: str,
    title: str,
    watch_query: str,
    reason: str,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    return await publish_event(
        db,
        event_type="scout.product.discarded",
        workspace_id=workspace_id,
        producer="scout",
        payload={
            "source": source,
            "source_id": source_id,
            "title": title[:200],
            "watch_query": watch_query,
            "reason": reason[:200],
        },
        correlation_id=correlation_id,
    )


async def publish_marketplace_price_changed(
    db: AsyncIOMotorDatabase,
    *,
    workspace_id: str,
    sku_normalizado: str,
    source: str,
    source_id: str,
    price_before: float,
    price_after: float,
    delta_pct: float,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    return await publish_event(
        db,
        event_type="marketplace.price.changed",
        workspace_id=workspace_id,
        producer="marketplace_agent",
        payload={
            "sku_normalizado": sku_normalizado,
            "source": source,
            "source_id": source_id,
            "price_before": price_before,
            "price_after": price_after,
            "delta_pct": delta_pct,
        },
        correlation_id=correlation_id,
    )


# ─── Helpers Build 1.3 ───────────────────────────────────────────────────


async def publish_trends_keyword_spike(
    db: AsyncIOMotorDatabase,
    *,
    workspace_id: str,
    keyword: str,
    interest_over_time: int,
    delta_7d_pct: float,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    return await publish_event(
        db,
        event_type="trends.keyword.spike",
        workspace_id=workspace_id,
        producer="trends_agent",
        payload={
            "keyword": keyword,
            "interest_over_time": interest_over_time,
            "delta_7d_pct": delta_7d_pct,
        },
        correlation_id=correlation_id,
    )


async def publish_marketplace_price_alert(
    db: AsyncIOMotorDatabase,
    *,
    workspace_id: str,
    sku_normalizado: str,
    titulo: str,
    precio_anterior: float,
    precio_actual: float,
    delta_pct: float,
    fuente: str,
    competitor_url: str,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    return await publish_event(
        db,
        event_type="marketplace.price.alert",
        workspace_id=workspace_id,
        producer="alerts_agent",
        payload={
            "sku_normalizado": sku_normalizado,
            "titulo": titulo[:200],
            "precio_anterior": precio_anterior,
            "precio_actual": precio_actual,
            "delta_pct": delta_pct,
            "fuente": fuente,
            "competitor_url": competitor_url,
        },
        correlation_id=correlation_id,
    )


# ─── Helpers Build 2.1 ───────────────────────────────────────────────────


async def publish_competitors_ad_detected(
    db: AsyncIOMotorDatabase,
    *,
    workspace_id: str,
    plataforma: str,
    ad_id_externo: str,
    anunciante: str,
    copy_titulo: str,
    fuente_query: str,
    durabilidad_dias: int,
    formato: str,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    return await publish_event(
        db,
        event_type="competitors.ad.detected",
        workspace_id=workspace_id,
        producer="competitors_agent",
        payload={
            "plataforma": plataforma,
            "ad_id_externo": ad_id_externo,
            "anunciante": anunciante[:200],
            "copy_titulo": copy_titulo[:200],
            "fuente_query": fuente_query,
            "durabilidad_dias": durabilidad_dias,
            "formato": formato,
        },
        correlation_id=correlation_id,
    )
