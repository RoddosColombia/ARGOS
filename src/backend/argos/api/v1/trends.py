"""API trends · GET /api/v1/trends/keywords."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from argos.auth.deps import require_role
from argos.auth.schemas import UserOut
from argos.db import collections as col
from argos.db.mongo import get_database, get_mongo_client

router = APIRouter(prefix="/api/v1/trends", tags=["trends"])


@router.get("/keywords")
async def list_keywords(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
) -> list[dict[str, Any]]:
    """Lista las keywords tracked del workspace · ordenadas por interés desc · rol ceo."""
    if get_mongo_client() is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB no conectado",
        )
    db = get_database()
    cursor = (
        db[col.KEYWORDS]
        .find({"workspace_id": user.workspace_id})
        .sort("interest_over_time", -1)
    )
    docs = await cursor.to_list(length=None)
    return [
        {
            "workspace_id": d["workspace_id"],
            "keyword": d["keyword"],
            "interest_over_time": int(d.get("interest_over_time") or 0),
            "growth_pct_7d": float(d.get("growth_pct_7d") or 0),
            "spike_detected": bool(d.get("spike_detected") or False),
            "vertical": d.get("vertical", ""),
            "updated_at": d["updated_at"].isoformat() if d.get("updated_at") else None,
        }
        for d in docs
    ]
