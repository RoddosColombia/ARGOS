"""Búsqueda de catálogo para cotización WhatsApp (Build 3.2).

Busca en products_catalog por nombre/categoría usando regex case-insensitive.
Enriquece con stock actual de sismo_inventory (último snapshot).

Refs: phase_3/build_3.2 · ROG-A3 (workspace_id)
"""
from __future__ import annotations

import logging
import re
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.db import collections as col

logger = logging.getLogger("argos.agents.whatsapp.catalog_search")

MAX_RESULTS = 5
MIN_QUERY_LENGTH = 3


def _build_search_regex(query_text: str) -> str:
    """Construye regex para buscar keywords en nombre de producto."""
    words = [w.strip() for w in query_text.split() if len(w.strip()) >= MIN_QUERY_LENGTH]
    if not words:
        return ""
    escaped = [re.escape(w) for w in words[:5]]
    return "|".join(escaped)


async def _get_latest_sync_date(
    db: AsyncIOMotorDatabase,
    workspace_id: str,
) -> str | None:
    pipeline = [
        {"$match": {"workspace_id": workspace_id}},
        {"$group": {"_id": None, "max_date": {"$max": "$fecha_sync_date"}}},
    ]
    result = await db[col.SISMO_INVENTORY].aggregate(pipeline).to_list(length=1)
    if result:
        return result[0].get("max_date")
    return None


async def _get_sismo_stock(
    db: AsyncIOMotorDatabase,
    workspace_id: str,
    product_names: list[str],
    fecha_sync_date: str,
) -> dict[str, dict[str, Any]]:
    """Busca stock en sismo_inventory para los productos encontrados.

    Hace match por nombre fuzzy (regex) contra el campo nombre de sismo_inventory.
    Retorna dict keyed by nombre_lower con {stock, precio_sismo, sku_sismo}.
    """
    if not product_names:
        return {}
    patterns = []
    for name in product_names[:MAX_RESULTS]:
        words = name.split()[:3]
        if words:
            escaped = [re.escape(w) for w in words if len(w) >= 3]
            if escaped:
                patterns.append("(?=.*" + ")(?=.*".join(escaped) + ")")
    if not patterns:
        return {}

    combined = "|".join(patterns)
    cursor = db[col.SISMO_INVENTORY].find(
        {
            "workspace_id": workspace_id,
            "fecha_sync_date": fecha_sync_date,
            "nombre": {"$regex": combined, "$options": "i"},
        },
        {"nombre": 1, "stock": 1, "precio": 1, "sku": 1, "_id": 0},
    ).limit(20)

    docs = await cursor.to_list(length=20)
    result: dict[str, dict[str, Any]] = {}
    for doc in docs:
        key = doc.get("nombre", "").lower()
        result[key] = {
            "stock": doc.get("stock", 0),
            "precio_sismo": doc.get("precio", 0),
            "sku_sismo": doc.get("sku", ""),
        }
    return result


async def search_catalog(
    db: AsyncIOMotorDatabase,
    query_text: str,
    workspace_id: str = "RODDOS",
) -> list[dict[str, Any]]:
    """Busca productos en products_catalog y enriquece con stock de SISMO.

    Retorna lista de matches con: nombre, precio, stock, source, categoria.
    Lista vacía si no hay matches.
    """
    pattern = _build_search_regex(query_text)
    if not pattern:
        return []

    cursor = db[col.PRODUCTS_CATALOG].find(
        {
            "workspace_id": workspace_id,
            "nombre": {"$regex": pattern, "$options": "i"},
        },
        {
            "nombre": 1,
            "precio_actual": 1,
            "stock_disponible": 1,
            "source": 1,
            "categoria": 1,
            "compatible_motos": 1,
            "permalink": 1,
            "_id": 0,
        },
    ).sort("updated_at", -1).limit(MAX_RESULTS)

    products = await cursor.to_list(length=MAX_RESULTS)
    if not products:
        return []

    fecha = await _get_latest_sync_date(db, workspace_id)
    sismo_stock: dict[str, dict[str, Any]] = {}
    if fecha:
        names = [p.get("nombre", "") for p in products if p.get("nombre")]
        sismo_stock = await _get_sismo_stock(db, workspace_id, names, fecha)

    results: list[dict[str, Any]] = []
    for p in products:
        nombre = p.get("nombre", "")
        nombre_lower = nombre.lower()
        sismo = sismo_stock.get(nombre_lower, {})
        stock_catalog = p.get("stock_disponible", 0)
        stock_sismo = sismo.get("stock")

        results.append({
            "nombre": nombre,
            "precio": p.get("precio_actual", 0),
            "stock": stock_sismo if stock_sismo is not None else stock_catalog,
            "stock_source": "sismo" if stock_sismo is not None else "catalog",
            "source": p.get("source", ""),
            "categoria": p.get("categoria", ""),
            "compatible_motos": p.get("compatible_motos", []),
            "permalink": p.get("permalink", ""),
        })

    logger.info(
        "catalog_search_done",
        extra={"query": query_text[:50], "results": len(results)},
    )
    return results
