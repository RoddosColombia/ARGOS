"""SismoAgent · Build 4.1 (lectura read-only desde SISMO V2).

Pipeline:
1. `SismoClient.get_inventory()` → lista de SKUs con stock/precio/costo/dias
2. Persistencia idempotente en `sismo_inventory` con clave (workspace, sku, fecha_sync_date)
3. Snapshot fechado · permite trazar evolución de stock por SKU día a día
4. Marca `is_slow_mover` si `dias_inventario >= 45` (consistente con
   `/api/inventory/slow_movers` de SISMO · evita doble query si la API ya lo
   filtra · podemos derivarlo localmente desde `dias_inventario`)
5. Emite `sismo.inventory.synced` al bus con stats (total_skus, slow_count)

Skip silencioso: si `SismoClient.enabled=False` el job devuelve stats vacías y
NO toca Mongo · útil para CI y entornos dev sin SISMO real.

Multi-tenant ROG-A3: cada doc lleva `workspace_id` y todas las queries lo filtran.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.config import get_settings
from argos.db import collections as col
from argos.db.events import publish_sismo_inventory_synced
from argos.partners.sismo.client import SismoClient

logger = logging.getLogger("argos.agents.sismo")

SLOW_MOVER_DAYS_THRESHOLD = 45


@dataclass
class SyncStats:
    enabled: bool
    total_skus: int
    slow_count: int
    inserted: int
    updated: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "total_skus": self.total_skus,
            "slow_count": self.slow_count,
            "inserted": self.inserted,
            "updated": self.updated,
        }


class SismoAgent:
    """Wrapper de alto nivel sobre `SismoClient` · stateless."""

    def __init__(self, client: SismoClient | None = None) -> None:
        if client is None:
            settings = get_settings()
            client = SismoClient(
                base_url=settings.sismo_api_url, api_key=settings.sismo_api_key
            )
        self._client = client

    @property
    def enabled(self) -> bool:
        return self._client.enabled

    async def get_inventory(self) -> list[dict[str, Any]]:
        async with self._client:
            return await self._client.get_inventory()

    async def get_slow_movers(self) -> list[dict[str, Any]]:
        async with self._client:
            return await self._client.get_slow_movers()

    async def get_daily_sales(self, fecha: str) -> list[dict[str, Any]]:
        async with self._client:
            return await self._client.get_daily_sales(fecha)


def _normalize_inventory_item(item: dict[str, Any]) -> dict[str, Any] | None:
    """Acepta variaciones de naming · devuelve None si falta sku."""
    sku = str(item.get("sku") or item.get("sku_normalizado") or item.get("codigo") or "").strip()
    if not sku:
        return None
    try:
        stock = int(item.get("stock") or item.get("existencias") or 0)
    except (TypeError, ValueError):
        stock = 0
    try:
        precio = float(item.get("precio") or item.get("precio_venta") or 0)
    except (TypeError, ValueError):
        precio = 0.0
    try:
        costo = float(item.get("costo") or item.get("costo_unitario") or 0)
    except (TypeError, ValueError):
        costo = 0.0
    try:
        dias = int(item.get("dias_inventario") or item.get("dias_sin_rotacion") or 0)
    except (TypeError, ValueError):
        dias = 0
    return {
        "sku": sku,
        "nombre": str(item.get("nombre") or item.get("descripcion") or "")[:200],
        "stock": stock,
        "precio": precio,
        "costo": costo,
        "dias_inventario": dias,
        "is_slow_mover": dias >= SLOW_MOVER_DAYS_THRESHOLD,
    }


async def sync_sismo_inventory_job(
    db: AsyncIOMotorDatabase,
    *,
    workspace_id: str = "RODDOS",
    agent: SismoAgent | None = None,
) -> SyncStats:
    """Job: consulta SISMO inventario completo + persiste snapshot del día.

    Idempotencia: la unique index en `sismo_inventory` por
    (workspace_id, sku, fecha_sync_date) hace que re-runs del mismo día sean
    `update` no `insert`. `fecha_sync_date` es la fecha (YYYY-MM-DD) sin hora
    para que el snapshot sea uno por día.
    """
    if agent is None:
        agent = SismoAgent()

    if not agent.enabled:
        logger.warning("sismo_sync_skipped_no_credentials")
        return SyncStats(enabled=False, total_skus=0, slow_count=0, inserted=0, updated=0)

    inventory = await agent.get_inventory()
    now = datetime.now(tz=UTC)
    fecha_sync_date = now.strftime("%Y-%m-%d")

    inserted = 0
    updated = 0
    slow_count = 0
    for raw in inventory:
        normalized = _normalize_inventory_item(raw)
        if normalized is None:
            continue
        if normalized["is_slow_mover"]:
            slow_count += 1
        result = await db[col.SISMO_INVENTORY].update_one(
            {
                "workspace_id": workspace_id,
                "sku": normalized["sku"],
                "fecha_sync_date": fecha_sync_date,
            },
            {
                "$set": {
                    **normalized,
                    "workspace_id": workspace_id,
                    "fecha_sync_date": fecha_sync_date,
                    "fecha_sync": now,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        if result.upserted_id is not None:
            inserted += 1
        elif result.modified_count > 0:
            updated += 1

    total = inserted + updated
    await publish_sismo_inventory_synced(
        db,
        workspace_id=workspace_id,
        total_skus=total,
        slow_count=slow_count,
    )
    stats = SyncStats(
        enabled=True,
        total_skus=total,
        slow_count=slow_count,
        inserted=inserted,
        updated=updated,
    )
    logger.info("sismo_sync_done", extra=stats.as_dict())
    return stats
