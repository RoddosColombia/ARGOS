"""API SISMO inventory · GET list · Build 4.1.

Endpoint read-only sobre el último snapshot persistido en `sismo_inventory`.
NO llama a SISMO V2 en runtime · sirve datos del último sync (cron 6h).
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from argos.auth.deps import require_role
from argos.auth.schemas import UserOut
from argos.db import collections as col
from argos.db.mongo import get_database, get_mongo_client

router = APIRouter(prefix="/api/v1/sismo", tags=["sismo"])

MAX_LIMIT = 500
InventoryType = Literal["all", "slow_movers"]


def _ensure_mongo() -> None:
    if get_mongo_client() is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB no conectado",
        )


def _serialize(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "sku": doc.get("sku", ""),
        "nombre": doc.get("nombre", ""),
        "stock": int(doc.get("stock") or 0),
        "precio": float(doc.get("precio") or 0),
        "costo": float(doc.get("costo") or 0),
        "dias_inventario": int(doc.get("dias_inventario") or 0),
        "is_slow_mover": bool(doc.get("is_slow_mover") or False),
        "fecha_sync_date": doc.get("fecha_sync_date", ""),
        "fecha_sync": doc["fecha_sync"].isoformat() if doc.get("fecha_sync") else None,
    }


@router.get("/inventory")
async def list_inventory(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
    inv_type: Annotated[InventoryType, Query(alias="type")] = "all",
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 100,
) -> dict[str, Any]:
    """Lista del inventario del último snapshot · `type=slow_movers` filtra los rezagados.

    Devuelve el snapshot del `fecha_sync_date` más reciente del workspace.
    Si nunca se ha sincronizado, `items=[]` y `fecha_sync_date=null`.
    """
    _ensure_mongo()
    db = get_database()

    # Resolver fecha del último sync
    pipeline = [
        {"$match": {"workspace_id": user.workspace_id}},
        {"$group": {"_id": None, "max_date": {"$max": "$fecha_sync_date"}}},
    ]
    latest = await db[col.SISMO_INVENTORY].aggregate(pipeline).to_list(length=1)
    if not latest or not latest[0].get("max_date"):
        return {"fecha_sync_date": None, "type": inv_type, "items": [], "total": 0}

    fecha = latest[0]["max_date"]
    query: dict[str, Any] = {"workspace_id": user.workspace_id, "fecha_sync_date": fecha}
    if inv_type == "slow_movers":
        query["is_slow_mover"] = True

    cursor = db[col.SISMO_INVENTORY].find(query).sort("dias_inventario", -1).limit(limit)
    docs = await cursor.to_list(length=limit)
    return {
        "fecha_sync_date": fecha,
        "type": inv_type,
        "items": [_serialize(d) for d in docs],
        "total": len(docs),
    }


def _serialize_sale(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "sku": doc.get("sku", ""),
        "date": doc.get("date", ""),
        "units_sold": int(doc.get("units_sold") or 0),
        "revenue": float(doc.get("revenue") or 0),
        "channel": doc.get("channel", ""),
        "fecha_sync": doc["fecha_sync"].isoformat() if doc.get("fecha_sync") else None,
    }


@router.get("/sales")
async def list_sales(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
    fecha: Annotated[
        str | None,
        Query(
            alias="date",
            pattern=r"^\d{4}-\d{2}-\d{2}$",
            description="YYYY-MM-DD · default: día más reciente con datos",
        ),
    ] = None,
    sku: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 100,
) -> dict[str, Any]:
    """Lista ventas del día solicitado · si `date` no se pasa, usa el último día con datos.

    Respuesta: `{date, sku, items, totals: {units_sold, revenue_cop, count}}`.
    Filtros: `date=YYYY-MM-DD` · `sku=XXX` para una sola línea.
    """
    _ensure_mongo()
    db = get_database()

    if fecha is None:
        latest = await db[col.SISMO_SALES_DAILY].aggregate(
            [
                {"$match": {"workspace_id": user.workspace_id}},
                {"$group": {"_id": None, "max_date": {"$max": "$date"}}},
            ]
        ).to_list(length=1)
        if not latest or not latest[0].get("max_date"):
            return {
                "date": None, "sku": sku, "items": [],
                "totals": {"units_sold": 0, "revenue_cop": 0.0, "count": 0},
            }
        fecha = latest[0]["max_date"]

    query: dict[str, Any] = {"workspace_id": user.workspace_id, "date": fecha}
    if sku:
        query["sku"] = sku

    cursor = db[col.SISMO_SALES_DAILY].find(query).sort("revenue", -1).limit(limit)
    docs = await cursor.to_list(length=limit)

    units = sum(int(d.get("units_sold") or 0) for d in docs)
    revenue = round(sum(float(d.get("revenue") or 0) for d in docs), 2)
    return {
        "date": fecha,
        "sku": sku,
        "items": [_serialize_sale(d) for d in docs],
        "totals": {
            "units_sold": units,
            "revenue_cop": revenue,
            "count": len(docs),
        },
    }
