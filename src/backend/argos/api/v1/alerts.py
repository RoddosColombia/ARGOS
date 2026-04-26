"""API alerts · GET /api/v1/alerts/recent · últimas alertas de precio."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from argos.auth.deps import require_role
from argos.auth.schemas import UserOut
from argos.db import collections as col
from argos.db.mongo import get_database, get_mongo_client

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])

ALERT_LOOKBACK_HOURS = 48
MAX_LIMIT = 100


@router.get("/recent")
async def recent_alerts(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 20,
) -> list[dict[str, Any]]:
    """Lista las últimas alertas de precio del workspace · ventana 48h · rol ceo."""
    if get_mongo_client() is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB no conectado",
        )
    db = get_database()
    cutoff = datetime.now(tz=UTC) - timedelta(hours=ALERT_LOOKBACK_HOURS)

    cursor = (
        db[col.ARGOS_EVENTS]
        .find(
            {
                "workspace_id": user.workspace_id,
                "event_type": "marketplace.price.alert",
                "timestamp_utc": {"$gte": cutoff},
            }
        )
        .sort("timestamp_utc", -1)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    return [
        {
            "event_id": d["event_id"],
            "timestamp_utc": d["timestamp_utc"].isoformat(),
            "sku_normalizado": d["payload"].get("sku_normalizado", ""),
            "titulo": d["payload"].get("titulo", ""),
            "precio_anterior": float(d["payload"].get("precio_anterior") or 0),
            "precio_actual": float(d["payload"].get("precio_actual") or 0),
            "delta_pct": float(d["payload"].get("delta_pct") or 0),
            "fuente": d["payload"].get("fuente", ""),
            "competitor_url": d["payload"].get("competitor_url", ""),
        }
        for d in docs
    ]
