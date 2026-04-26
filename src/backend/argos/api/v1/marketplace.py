"""API marketplace · GET /api/v1/marketplace/top-products."""
from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from argos.auth.deps import require_role
from argos.auth.schemas import UserOut
from argos.db import collections as col
from argos.db.mongo import get_database, get_mongo_client

router = APIRouter(prefix="/api/v1/marketplace", tags=["marketplace"])

SourceFilter = Literal["meli", "fb", "all"]
TOP_LIMIT = 50

# Mapeo entre el valor del query param (UI-friendly) y el `source` que se
# persiste en products_catalog (canónico).
_SOURCE_MAP: dict[str, str] = {
    "meli": "meli",
    "fb": "fb_marketplace",
}


@router.get("/top-products")
async def top_products(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
    source: Annotated[SourceFilter, Query(description="Filtra por fuente · meli/fb/all")] = "all",
) -> list[dict[str, Any]]:
    """Top N productos del workspace ordenados por `precio_promedio` desc.

    `precio_promedio` se calcula como avg de `products_history.precio` para cada
    producto. `cambio_precio_pct` = (precio_actual - precio_promedio) / precio_promedio * 100
    · positivo = producto está sobre su precio promedio histórico (spike reciente).
    """
    if get_mongo_client() is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB no conectado",
        )
    db = get_database()

    match_stage: dict[str, Any] = {"workspace_id": user.workspace_id}
    if source != "all":
        match_stage["source"] = _SOURCE_MAP[source]

    pipeline: list[dict[str, Any]] = [
        {"$match": match_stage},
        {
            "$lookup": {
                "from": col.PRODUCTS_HISTORY,
                "localField": "_id",
                "foreignField": "product_id",
                "as": "history",
            }
        },
        {
            "$addFields": {
                "precio_promedio": {
                    "$ifNull": [{"$avg": "$history.precio"}, "$precio_actual"]
                }
            }
        },
        {
            "$addFields": {
                "cambio_precio_pct": {
                    "$cond": [
                        {"$gt": ["$precio_promedio", 0]},
                        {
                            "$multiply": [
                                {
                                    "$divide": [
                                        {"$subtract": ["$precio_actual", "$precio_promedio"]},
                                        "$precio_promedio",
                                    ]
                                },
                                100,
                            ]
                        },
                        0,
                    ]
                }
            }
        },
        {"$sort": {"precio_promedio": -1, "_id": 1}},
        {"$limit": TOP_LIMIT},
        {
            "$project": {
                "_id": 0,
                "sku_normalizado": 1,
                "titulo": "$nombre",
                "precio_actual": 1,
                "precio_promedio": 1,
                "fuente": "$source",
                "cambio_precio_pct": 1,
                "ultima_actualizacion": "$updated_at",
                "permalink": 1,
            }
        },
    ]

    docs = await db[col.PRODUCTS_CATALOG].aggregate(pipeline).to_list(length=TOP_LIMIT)
    # Serialización · datetime → isoformat, redondeo de pcts para UI
    out: list[dict[str, Any]] = []
    for d in docs:
        ts = d.get("ultima_actualizacion")
        out.append(
            {
                "sku_normalizado": d.get("sku_normalizado", ""),
                "titulo": d.get("titulo", ""),
                "precio_actual": float(d.get("precio_actual") or 0),
                "precio_promedio": round(float(d.get("precio_promedio") or 0), 2),
                "fuente": "fb" if d.get("fuente") == "fb_marketplace" else d.get("fuente", ""),
                "cambio_precio_pct": round(float(d.get("cambio_precio_pct") or 0), 2),
                "ultima_actualizacion": ts.isoformat() if ts else None,
                "permalink": d.get("permalink") or "",
            }
        )
    return out
