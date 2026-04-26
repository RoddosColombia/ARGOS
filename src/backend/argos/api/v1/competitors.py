"""API competitors · GET /api/v1/competitors/ads."""
from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from argos.auth.deps import require_role
from argos.auth.schemas import UserOut
from argos.db import collections as col
from argos.db.mongo import get_database, get_mongo_client

router = APIRouter(prefix="/api/v1/competitors", tags=["competitors"])

AdSource = Literal["meta", "google", "all"]
MAX_LIMIT = 200


@router.get("/ads")
async def list_ads(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
    source: Annotated[AdSource, Query(description="Filtra por plataforma")] = "meta",
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 50,
    only_active: Annotated[bool, Query(description="Solo ads activos")] = False,
) -> list[dict[str, Any]]:
    """Lista ads del workspace · ordenados por fecha_inicio desc · rol ceo."""
    if get_mongo_client() is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB no conectado",
        )
    db = get_database()

    query: dict[str, Any] = {"workspace_id": user.workspace_id}
    if source != "all":
        query["plataforma"] = source
    if only_active:
        query["activo"] = True

    cursor = db[col.ADS_LIBRARY].find(query).sort("fecha_inicio", -1).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [
        {
            "id": str(d["_id"]),
            "plataforma": d.get("plataforma", ""),
            "ad_id_externo": d.get("ad_id_externo", ""),
            "anunciante": d.get("anunciante", ""),
            "copy_texto": d.get("copy_texto", ""),
            "copy_titulo": d.get("copy_titulo", ""),
            "url_landing": d.get("url_landing", ""),
            "fecha_inicio": d["fecha_inicio"].isoformat() if d.get("fecha_inicio") else None,
            "durabilidad_dias": int(d.get("durabilidad_dias") or 0),
            "formato": d.get("formato", "unknown"),
            "activo": bool(d.get("activo", False)),
            "fuente_query": d.get("fuente_query", ""),
        }
        for d in docs
    ]
