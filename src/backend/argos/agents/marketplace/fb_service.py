"""FB Marketplace · normalización de items Apify al schema de products_catalog.

Build 1.1: scraper apify/facebook-marketplace-scraper. Output del actor varía
versión a versión; el parser intenta ser tolerante a campos faltantes.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.agents.marketplace.service import UpsertResult, persist_parsed_product

logger = logging.getLogger("argos.agents.marketplace.fb")

_PRICE_RE = re.compile(r"[\d.,]+")


def parse_apify_fb_item(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Convierte un item del actor FB Marketplace a un parsed dict estandarizado.

    Devuelve None si el item carece de id/title/precio parseable.
    """
    title = raw.get("title") or raw.get("name")
    if not title:
        return None

    # IDs en FB Marketplace: la URL del listing trae el ID al final
    url = raw.get("url") or raw.get("permalink") or ""
    source_id = _extract_fb_item_id(url) or raw.get("id") or raw.get("listingId")
    if not source_id:
        return None
    source_id = str(source_id)

    price = _parse_price(raw.get("price"))
    if price is None:
        return None

    return {
        "source": "fb_marketplace",
        "source_id": source_id,
        "nombre": str(title),
        "precio_actual": price,
        "stock_disponible": 1,  # FB Marketplace listings son 1 ítem por listing típicamente
        "seller_id": str(raw.get("seller") or raw.get("sellerName") or "")[:64],
        "imagen_url": raw.get("image") or raw.get("primaryPhoto") or "",
        "permalink": url,
        "categoria_meli_id": "",
        "condition": str(raw.get("condition") or "").lower(),
    }


def _extract_fb_item_id(url: str) -> str | None:
    if not url:
        return None
    # https://www.facebook.com/marketplace/item/1234567890/
    match = re.search(r"/marketplace/item/(\d+)", url)
    return match.group(1) if match else None


def _parse_price(raw_price: Any) -> float | None:
    if raw_price is None:
        return None
    if isinstance(raw_price, (int, float)):
        return float(raw_price)
    s = str(raw_price)
    match = _PRICE_RE.search(s.replace(".", "").replace(",", ""))  # quitar separadores miles/dec ES
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


async def upsert_fb_product(
    db: AsyncIOMotorDatabase,
    apify_item: dict[str, Any],
    *,
    workspace_id: str = "RODDOS",
    emit_events: bool = True,
) -> UpsertResult | None:
    parsed = parse_apify_fb_item(apify_item)
    if parsed is None:
        logger.warning("fb_item_invalid", extra={"raw_keys": list(apify_item.keys())})
        return None
    return await persist_parsed_product(
        db, parsed, workspace_id=workspace_id, emit_events=emit_events
    )
