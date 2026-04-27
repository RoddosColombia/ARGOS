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
from datetime import UTC, datetime, timedelta
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.config import get_settings
from argos.db import collections as col
from argos.db.events import (
    publish_sismo_inventory_synced,
    publish_sismo_sales_daily_synced,
)
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


# ─── Build 4.2 · ventas diarias ──────────────────────────────────────────


@dataclass
class SalesSyncStats:
    enabled: bool
    fecha: str
    sales_count: int
    units_total: int
    revenue_total: float
    inserted: int
    updated: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "fecha": self.fecha,
            "sales_count": self.sales_count,
            "units_total": self.units_total,
            "revenue_total": self.revenue_total,
            "inserted": self.inserted,
            "updated": self.updated,
        }


def _normalize_sales_item(item: dict[str, Any], default_fecha: str) -> dict[str, Any] | None:
    """Acepta variaciones de naming · descarta filas sin sku."""
    sku = str(item.get("sku") or item.get("sku_normalizado") or item.get("codigo") or "").strip()
    if not sku:
        return None
    try:
        units = int(item.get("units_sold") or item.get("unidades") or item.get("cantidad") or 0)
    except (TypeError, ValueError):
        units = 0
    try:
        revenue = float(
            item.get("revenue") or item.get("revenue_cop") or item.get("total") or item.get("monto") or 0
        )
    except (TypeError, ValueError):
        revenue = 0.0
    fecha = str(item.get("date") or item.get("fecha") or default_fecha)[:10]
    channel = str(item.get("channel") or item.get("canal") or "n/a")[:50]
    return {
        "sku": sku,
        "date": fecha,
        "units_sold": units,
        "revenue": revenue,
        "channel": channel,
    }


async def sync_sismo_sales_daily_job(
    db: AsyncIOMotorDatabase,
    *,
    workspace_id: str = "RODDOS",
    fecha: str | None = None,
    agent: SismoAgent | None = None,
) -> SalesSyncStats:
    """Job: descarga ventas del día anterior (UTC) y persiste en sismo_sales_daily.

    Idempotencia: unique index en (workspace_id, date, sku) hace que re-runs
    actualicen las filas en lugar de duplicar. Si SISMO devuelve filas
    "tarde" (ventas que se sincronizan al día siguiente) el segundo run las
    upserta correctamente.
    """
    if agent is None:
        agent = SismoAgent()

    if fecha is None:
        # Default: ayer UTC. La job corre 01:00 UTC (jueves 01:00 → ventas miércoles).
        fecha = (datetime.now(tz=UTC) - timedelta(days=1)).strftime("%Y-%m-%d")

    if not agent.enabled:
        logger.warning("sismo_sales_sync_skipped_no_credentials", extra={"date": fecha})
        return SalesSyncStats(
            enabled=False, fecha=fecha, sales_count=0, units_total=0,
            revenue_total=0.0, inserted=0, updated=0,
        )

    raw_items = await agent.get_daily_sales(fecha)
    now = datetime.now(tz=UTC)

    inserted = 0
    updated = 0
    units_total = 0
    revenue_total = 0.0
    sales_count = 0

    for raw in raw_items:
        normalized = _normalize_sales_item(raw, default_fecha=fecha)
        if normalized is None:
            continue
        sales_count += 1
        units_total += normalized["units_sold"]
        revenue_total += normalized["revenue"]
        result = await db[col.SISMO_SALES_DAILY].update_one(
            {
                "workspace_id": workspace_id,
                "date": normalized["date"],
                "sku": normalized["sku"],
            },
            {
                "$set": {
                    **normalized,
                    "workspace_id": workspace_id,
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

    await publish_sismo_sales_daily_synced(
        db,
        workspace_id=workspace_id,
        fecha=fecha,
        sales_count=sales_count,
        units_total=units_total,
        revenue_total=revenue_total,
    )
    stats = SalesSyncStats(
        enabled=True,
        fecha=fecha,
        sales_count=sales_count,
        units_total=units_total,
        revenue_total=revenue_total,
        inserted=inserted,
        updated=updated,
    )
    logger.info("sismo_sales_sync_done", extra=stats.as_dict())
    return stats
