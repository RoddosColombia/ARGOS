"""Marketplace Agent · servicio de upsert desde resultados MELI.

Convenciones Build 1.0:
- `sku_normalizado`: `{source}:{source_id}` hasta que Build 1.1 introduzca Haiku
  para agrupar variantes del mismo producto bajo un SKU canónico real.
- `categoria`: vacío en Build 1.0 · Build 1.1 (Haiku) llena la jerarquía
  `repuestos.frenos.pastillas` etc. El `categoria_meli_id` se persiste como hint.
- Price change threshold: ≥ 5% en valor absoluto dispara `marketplace.price.changed`.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.agents.marketplace.categorizer import detect_compatible_motos
from argos.db import collections as col
from argos.db.events import (
    publish_marketplace_price_changed,
    publish_marketplace_product_detected,
)

logger = logging.getLogger("argos.agents.marketplace")

PRICE_CHANGE_THRESHOLD_PCT = 5.0


@dataclass
class UpsertResult:
    product_id: str
    sku_normalizado: str
    created: bool
    price_change_delta_pct: float | None  # None si no cambió ≥ threshold


def _normalize_sku(source: str, source_id: str) -> str:
    return f"{source}:{source_id}"


def _parse_meli_item(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Extrae campos relevantes de un item de la API MELI. Devuelve None si inválido."""
    item_id = raw.get("id")
    title = raw.get("title")
    price = raw.get("price")
    if not item_id or not title or price is None:
        return None
    seller = raw.get("seller") or {}
    return {
        "source": "meli",
        "source_id": str(item_id),
        "nombre": str(title),
        "precio_actual": float(price),
        "stock_disponible": int(raw.get("available_quantity") or 0),
        "seller_id": str(seller.get("id") or "")[:64],
        "imagen_url": raw.get("thumbnail") or "",
        "permalink": raw.get("permalink") or "",
        "categoria_meli_id": raw.get("category_id") or "",
        "condition": raw.get("condition") or "",
    }


async def upsert_product(
    db: AsyncIOMotorDatabase,
    meli_item: dict[str, Any],
    *,
    workspace_id: str = "RODDOS",
    emit_events: bool = True,
) -> UpsertResult | None:
    """Upsert de un item MELI a `products_catalog`. Emite eventos si procede.

    Retorna `None` si el item MELI es inválido (sin id/title/price).
    """
    parsed = _parse_meli_item(meli_item)
    if parsed is None:
        logger.warning("meli_item_invalid", extra={"raw_keys": list(meli_item.keys())})
        return None

    sku_normalizado = _normalize_sku(parsed["source"], parsed["source_id"])
    compatible_motos = detect_compatible_motos(parsed["nombre"])
    now = datetime.now(tz=UTC)

    existing = await db[col.PRODUCTS_CATALOG].find_one(
        {"workspace_id": workspace_id, "source": parsed["source"], "source_id": parsed["source_id"]}
    )

    set_fields = {
        "workspace_id": workspace_id,
        "sku_normalizado": sku_normalizado,
        "source": parsed["source"],
        "source_id": parsed["source_id"],
        "nombre": parsed["nombre"],
        "categoria": "",  # Build 1.1 · Haiku categorizer llena esto
        "categoria_meli_id": parsed["categoria_meli_id"],
        "compatible_motos": compatible_motos,
        "precio_actual": parsed["precio_actual"],
        "stock_disponible": parsed["stock_disponible"],
        "seller_id": parsed["seller_id"],
        "imagen_url": parsed["imagen_url"],
        "permalink": parsed["permalink"],
        "condition": parsed["condition"],
        "updated_at": now,
    }

    set_on_insert = {"created_at": now}

    price_change_delta_pct: float | None = None
    created = existing is None

    if existing is not None:
        previous_price = float(existing.get("precio_actual") or 0)
        if previous_price > 0:
            delta_pct = ((parsed["precio_actual"] - previous_price) / previous_price) * 100.0
            if abs(delta_pct) >= PRICE_CHANGE_THRESHOLD_PCT:
                price_change_delta_pct = round(delta_pct, 4)

    result = await db[col.PRODUCTS_CATALOG].update_one(
        {"workspace_id": workspace_id, "source": parsed["source"], "source_id": parsed["source_id"]},
        {"$set": set_fields, "$setOnInsert": set_on_insert},
        upsert=True,
    )

    doc = await db[col.PRODUCTS_CATALOG].find_one(
        {"workspace_id": workspace_id, "source": parsed["source"], "source_id": parsed["source_id"]},
        {"_id": 1},
    )
    product_id = str(doc["_id"]) if doc else ""

    # ─── Historia · solo si price o stock cambiaron (o es nuevo) ─────────
    should_write_history = created or (
        existing is not None
        and (
            parsed["precio_actual"] != float(existing.get("precio_actual") or 0)
            or parsed["stock_disponible"] != int(existing.get("stock_disponible") or 0)
        )
    )
    if should_write_history and doc is not None:
        await db[col.PRODUCTS_HISTORY].insert_one(
            {
                "workspace_id": workspace_id,
                "product_id": doc["_id"],
                "timestamp": now,
                "precio": parsed["precio_actual"],
                "stock": parsed["stock_disponible"],
                "source": parsed["source"],
            }
        )

    # ─── Eventos al bus ──────────────────────────────────────────────────
    if emit_events and (created or result.modified_count > 0):
        await publish_marketplace_product_detected(
            db,
            workspace_id=workspace_id,
            sku_normalizado=sku_normalizado,
            source=parsed["source"],
            source_id=parsed["source_id"],
            nombre=parsed["nombre"],
            categoria="",
            precio_actual=parsed["precio_actual"],
            created=created,
        )

    if emit_events and price_change_delta_pct is not None and existing is not None:
        await publish_marketplace_price_changed(
            db,
            workspace_id=workspace_id,
            sku_normalizado=sku_normalizado,
            source=parsed["source"],
            source_id=parsed["source_id"],
            price_before=float(existing.get("precio_actual") or 0),
            price_after=parsed["precio_actual"],
            delta_pct=price_change_delta_pct,
        )

    return UpsertResult(
        product_id=product_id,
        sku_normalizado=sku_normalizado,
        created=created,
        price_change_delta_pct=price_change_delta_pct,
    )
