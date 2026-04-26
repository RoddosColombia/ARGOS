"""Alerts Agent · detecta caídas de precio significativas en últimas 24h.

Algoritmo:
- Aggregation sobre `products_history` filtrando por timestamp >= now - 24h
- Por cada `product_id` toma el primero (más antiguo) y el último (más reciente)
- Si `(last - first) / first <= -threshold_pct` → emite `marketplace.price.alert`
- Cruza con `products_catalog` para enriquecer payload (titulo, source, permalink)

Idempotencia: emite un evento por SKU por corrida del job · si la misma caída
sigue presente en la siguiente hora, vuelve a emitir. Aceptable por ahora · el
consumidor (Strategist en Phase 2+) puede deduplicar por (sku, timestamp_día).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.db import collections as col
from argos.db.events import publish_marketplace_price_alert

logger = logging.getLogger("argos.agents.alerts")

DEFAULT_THRESHOLD_PCT = 15.0
LOOKBACK_HOURS = 24


@dataclass
class AlertResult:
    sku_normalizado: str
    titulo: str
    precio_anterior: float
    precio_actual: float
    delta_pct: float
    fuente: str
    competitor_url: str


async def check_price_drops(
    db: AsyncIOMotorDatabase,
    *,
    workspace_id: str = "RODDOS",
    threshold_pct: float = DEFAULT_THRESHOLD_PCT,
    lookback_hours: int = LOOKBACK_HOURS,
    emit_events: bool = True,
) -> list[AlertResult]:
    """Detecta drops ≥ threshold_pct en las últimas `lookback_hours` y emite alertas."""
    cutoff = datetime.now(tz=UTC) - timedelta(hours=lookback_hours)

    pipeline: list[dict[str, Any]] = [
        {"$match": {"workspace_id": workspace_id, "timestamp": {"$gte": cutoff}}},
        {"$sort": {"product_id": 1, "timestamp": 1}},
        {
            "$group": {
                "_id": "$product_id",
                "first": {"$first": "$$ROOT"},
                "last": {"$last": "$$ROOT"},
            }
        },
    ]
    groups = await db[col.PRODUCTS_HISTORY].aggregate(pipeline).to_list(length=None)

    alerts: list[AlertResult] = []
    for g in groups:
        first_price = float(g["first"]["precio"] or 0)
        last_price = float(g["last"]["precio"] or 0)
        if first_price <= 0:
            continue
        delta_pct = ((last_price - first_price) / first_price) * 100.0
        if delta_pct > -threshold_pct:
            continue  # caída no suficiente

        product_id = g["_id"]
        product = await db[col.PRODUCTS_CATALOG].find_one({"_id": product_id})
        if product is None:
            continue

        fuente = "fb" if product.get("source") == "fb_marketplace" else product.get("source", "")
        alert = AlertResult(
            sku_normalizado=product.get("sku_normalizado", ""),
            titulo=product.get("nombre", ""),
            precio_anterior=round(first_price, 2),
            precio_actual=round(last_price, 2),
            delta_pct=round(delta_pct, 2),
            fuente=fuente,
            competitor_url=product.get("permalink", ""),
        )
        alerts.append(alert)

        if emit_events:
            await publish_marketplace_price_alert(
                db,
                workspace_id=workspace_id,
                sku_normalizado=alert.sku_normalizado,
                titulo=alert.titulo,
                precio_anterior=alert.precio_anterior,
                precio_actual=alert.precio_actual,
                delta_pct=alert.delta_pct,
                fuente=alert.fuente,
                competitor_url=alert.competitor_url,
            )

    logger.info("price_alerts_checked", extra={"alerts_emitted": len(alerts)})
    return alerts
