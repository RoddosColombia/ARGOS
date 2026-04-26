"""API briefing · GET /today + GET /history."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from argos.auth.deps import require_role
from argos.auth.schemas import UserOut
from argos.db import collections as col
from argos.db.mongo import get_database, get_mongo_client

router = APIRouter(prefix="/api/v1/briefing", tags=["briefing"])

MAX_HISTORY = 30


def _ensure_mongo() -> None:
    if get_mongo_client() is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB no conectado",
        )


def _serialize(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "fecha": doc.get("fecha", ""),
        "mercado_24h": doc.get("mercado_24h", {}),
        "acciones_del_dia": list(doc.get("acciones_del_dia") or []),
        "estado_mercado": doc.get("estado_mercado", ""),
        "modelo_usado": doc.get("modelo_usado", ""),
        "tokens_input": int(doc.get("tokens_input") or 0),
        "tokens_output": int(doc.get("tokens_output") or 0),
        "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
    }


@router.get("/today")
async def briefing_today(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
) -> dict[str, Any]:
    """Devuelve el briefing del día UTC actual · 404 si no existe."""
    _ensure_mongo()
    db = get_database()
    fecha = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    doc = await db[col.BRIEFINGS].find_one({"workspace_id": user.workspace_id, "fecha": fecha})
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sin briefing para {fecha} · próximo job corre 06:45 UTC",
        )
    return _serialize(doc)


@router.get("/history")
async def briefing_history(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
    limit: Annotated[int, Query(ge=1, le=MAX_HISTORY)] = 7,
) -> list[dict[str, Any]]:
    """Últimos N briefings del workspace · ordenados por fecha desc · rol ceo."""
    _ensure_mongo()
    db = get_database()
    cursor = (
        db[col.BRIEFINGS]
        .find({"workspace_id": user.workspace_id})
        .sort("fecha", -1)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    return [_serialize(d) for d in docs]
