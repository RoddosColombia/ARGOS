"""API recommendations · GET list + POST approve/reject · GET hit-rate."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from argos.auth.deps import require_role
from argos.auth.schemas import UserOut
from argos.db import collections as col
from argos.db.events import (
    publish_recommendation_approved,
    publish_recommendation_rejected,
)
from argos.db.mongo import get_database, get_mongo_client

router = APIRouter(prefix="/api/v1/recommendations", tags=["recommendations"])

MAX_LIMIT = 100
HIT_RATE_DEFAULT_DAYS = 30

RecStatus = Literal[
    "pendiente",
    "aprobada",
    "ejecutada",
    "rechazada",
    "rechazada_compliance",
    "expirada",
    "evaluada",
]


def _ensure_mongo() -> None:
    if get_mongo_client() is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB no conectado",
        )


def _serialize(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "type": doc.get("type", ""),
        "action_description": doc.get("action_description", ""),
        "rationale": doc.get("rationale", ""),
        "priority": doc.get("priority", "Media"),
        "priority_score": float(doc.get("priority_score") or 0),
        "expected_impact": doc.get("expected_impact") or {},
        "actual_impact": doc.get("actual_impact"),
        "hit_rate_contribution": doc.get("hit_rate_contribution"),
        "learning": doc.get("learning"),
        "status": doc.get("status", "pendiente"),
        "approved_by": doc.get("approved_by"),
        "approved_at": doc["approved_at"].isoformat() if doc.get("approved_at") else None,
        "executed_at": doc["executed_at"].isoformat() if doc.get("executed_at") else None,
        "fecha_briefing": doc.get("fecha_briefing", ""),
        "shown_in_briefing": list(doc.get("shown_in_briefing") or []),
        "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
    }


def _parse_object_id(rec_id: str) -> ObjectId:
    try:
        return ObjectId(rec_id)
    except InvalidId as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID de recomendación inválido",
        ) from exc


@router.get("")
async def list_recommendations(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
    status_filter: Annotated[RecStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 20,
) -> list[dict[str, Any]]:
    """Lista recomendaciones del workspace · ordenadas por priority desc + created desc."""
    _ensure_mongo()
    db = get_database()
    query: dict[str, Any] = {"workspace_id": user.workspace_id}
    if status_filter:
        query["status"] = status_filter
    cursor = (
        db[col.RECOMMENDATIONS]
        .find(query)
        .sort([("priority_score", -1), ("created_at", -1)])
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    return [_serialize(d) for d in docs]


@router.get("/hit-rate")
async def hit_rate(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
    days: Annotated[int, Query(ge=1, le=365)] = HIT_RATE_DEFAULT_DAYS,
) -> dict[str, Any]:
    """Tasa de éxito promedio de recomendaciones evaluadas en los últimos N días."""
    _ensure_mongo()
    db = get_database()
    cutoff = datetime.now(tz=UTC) - timedelta(days=days)
    pipeline = [
        {
            "$match": {
                "workspace_id": user.workspace_id,
                "status": "evaluada",
                "evaluated_at": {"$gte": cutoff},
                "hit_rate_contribution": {"$ne": None},
            }
        },
        {
            "$group": {
                "_id": None,
                "avg_hit_rate": {"$avg": "$hit_rate_contribution"},
                "count": {"$sum": 1},
            }
        },
    ]
    docs = await db[col.RECOMMENDATIONS].aggregate(pipeline).to_list(length=1)
    if not docs:
        return {"days": days, "evaluated_count": 0, "avg_hit_rate": None}
    return {
        "days": days,
        "evaluated_count": int(docs[0]["count"]),
        "avg_hit_rate": round(float(docs[0]["avg_hit_rate"]), 4),
    }


@router.post("/{rec_id}/approve")
async def approve_recommendation(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
    rec_id: str,
) -> dict[str, Any]:
    """Aprueba una recomendación pendiente · status → aprobada · emite evento."""
    _ensure_mongo()
    db = get_database()
    obj_id = _parse_object_id(rec_id)
    now = datetime.now(tz=UTC)

    result = await db[col.RECOMMENDATIONS].update_one(
        {
            "_id": obj_id,
            "workspace_id": user.workspace_id,
            "status": "pendiente",
        },
        {
            "$set": {
                "status": "aprobada",
                "approved_by": user.email,
                "approved_at": now,
                "updated_at": now,
            }
        },
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recomendación no encontrada o no está en status 'pendiente'",
        )
    await publish_recommendation_approved(
        db,
        workspace_id=user.workspace_id,
        recommendation_id=rec_id,
        approved_by=user.email,
    )
    doc = await db[col.RECOMMENDATIONS].find_one({"_id": obj_id})
    return _serialize(doc) if doc else {"id": rec_id, "status": "aprobada"}


@router.post("/{rec_id}/reject")
async def reject_recommendation(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
    rec_id: str,
    reason: Annotated[str, Body(embed=True)] = "",
) -> dict[str, Any]:
    """Rechaza una recomendación pendiente · status → rechazada · emite evento."""
    _ensure_mongo()
    db = get_database()
    obj_id = _parse_object_id(rec_id)
    now = datetime.now(tz=UTC)

    result = await db[col.RECOMMENDATIONS].update_one(
        {
            "_id": obj_id,
            "workspace_id": user.workspace_id,
            "status": "pendiente",
        },
        {
            "$set": {
                "status": "rechazada",
                "rejected_by": user.email,
                "rejected_at": now,
                "rejected_reason": reason[:300],
                "updated_at": now,
            }
        },
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recomendación no encontrada o no está en status 'pendiente'",
        )
    await publish_recommendation_rejected(
        db,
        workspace_id=user.workspace_id,
        recommendation_id=rec_id,
        rejected_by=user.email,
        reason=reason,
    )
    doc = await db[col.RECOMMENDATIONS].find_one({"_id": obj_id})
    return _serialize(doc) if doc else {"id": rec_id, "status": "rechazada"}
