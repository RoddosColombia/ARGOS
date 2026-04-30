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
from argos.services.audit import ActionResult, ActorType, audit_write

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
        # Build 2.5.5 · ROG-G2: campo que enruta la cola de approval por role
        "approval_required_role": doc.get("approval_required_role"),
        "approved_by": doc.get("approved_by"),
        "approved_at": doc["approved_at"].isoformat() if doc.get("approved_at") else None,
        "executed_at": doc["executed_at"].isoformat() if doc.get("executed_at") else None,
        "fecha_briefing": doc.get("fecha_briefing", ""),
        "shown_in_briefing": list(doc.get("shown_in_briefing") or []),
        "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
    }


def _can_approve(user_role: str, approval_required_role: str | None) -> tuple[bool, str]:
    """ROG-G2 · valida que el role del JWT puede aprobar/rechazar la recomendación.

    Reglas:
    - Si `approval_required_role` es None → cualquier rol con acceso al endpoint
      (CEO o CGO) puede aprobar. Compatibilidad con recomendaciones legacy.
    - Si es "ceo" → solo CEO.
    - Si es "cgo" → CGO o CEO (CEO también puede actuar como override · default
      rechazo en 24h escala a CEO según ROG-G2).
    - Si es "none" → ya no requiere approval (caso Plano 1 ya ejecutado).
    """
    if approval_required_role in (None, "", "none"):
        return True, ""
    if approval_required_role == "ceo":
        if user_role == "ceo":
            return True, ""
        return False, "Esta acción requiere approval del CEO (Plano 3)"
    if approval_required_role == "cgo":
        if user_role in ("cgo", "ceo"):
            return True, ""
        return False, "Esta acción requiere approval del CGO (Plano 2)"
    return False, f"approval_required_role desconocido: {approval_required_role!r}"


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
    user: Annotated[UserOut, Depends(require_role("ceo", "cgo"))],
    status_filter: Annotated[RecStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 20,
    approval_role: Annotated[str | None, Query(description="Filtrar por approval_required_role: ceo|cgo|none")] = None,
) -> list[dict[str, Any]]:
    """Lista recomendaciones del workspace · ordenadas por priority desc + created desc.

    ROG-G1 · CEO + CGO ven la misma información. ROG-G2 · `approval_role` permite
    filtrar la cola personal de cada role en el frontend (ceo ve sus Plano 3,
    cgo ve sus Plano 2).
    """
    _ensure_mongo()
    db = get_database()
    query: dict[str, Any] = {"workspace_id": user.workspace_id}
    if status_filter:
        query["status"] = status_filter
    if approval_role is not None:
        if approval_role == "none":
            query["$or"] = [
                {"approval_required_role": {"$exists": False}},
                {"approval_required_role": None},
                {"approval_required_role": "none"},
            ]
        else:
            query["approval_required_role"] = approval_role
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
    user: Annotated[UserOut, Depends(require_role("ceo", "cgo"))],
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
    user: Annotated[UserOut, Depends(require_role("ceo", "cgo"))],
    rec_id: str,
) -> dict[str, Any]:
    """Aprueba una recomendación pendiente · status → aprobada · emite evento.

    ROG-G2 · valida que el role del JWT coincida con `approval_required_role`
    de la recomendación. CEO puede aprobar Plano 2 (override) y Plano 3.
    CGO solo puede aprobar Plano 2.
    """
    _ensure_mongo()
    db = get_database()
    obj_id = _parse_object_id(rec_id)
    now = datetime.now(tz=UTC)

    # Lectura previa para validar approval_required_role contra role del JWT.
    existing = await db[col.RECOMMENDATIONS].find_one(
        {"_id": obj_id, "workspace_id": user.workspace_id},
    )
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recomendación no encontrada")
    if existing.get("status") != "pendiente":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recomendación no está en status 'pendiente'",
        )

    can, reason = _can_approve(user.role, existing.get("approval_required_role"))
    if not can:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)

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
    await audit_write(
        db,
        workspace_id=user.workspace_id,
        actor_type=ActorType.USER,
        actor_id=user.email,
        actor_role=user.role,
        action="recommendation.approved",
        resource_type="recommendation",
        resource_id=rec_id,
        result=ActionResult.SUCCESS,
    )
    doc = await db[col.RECOMMENDATIONS].find_one({"_id": obj_id})
    return _serialize(doc) if doc else {"id": rec_id, "status": "aprobada"}


@router.post("/{rec_id}/reject")
async def reject_recommendation(
    user: Annotated[UserOut, Depends(require_role("ceo", "cgo"))],
    rec_id: str,
    reason: Annotated[str, Body(embed=True)] = "",
) -> dict[str, Any]:
    """Rechaza una recomendación pendiente · status → rechazada · emite evento.

    ROG-G2 · valida role vs approval_required_role (igual que approve).
    """
    _ensure_mongo()
    db = get_database()
    obj_id = _parse_object_id(rec_id)
    now = datetime.now(tz=UTC)

    existing = await db[col.RECOMMENDATIONS].find_one(
        {"_id": obj_id, "workspace_id": user.workspace_id},
    )
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recomendación no encontrada")
    if existing.get("status") != "pendiente":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recomendación no está en status 'pendiente'",
        )

    can, can_reason = _can_approve(user.role, existing.get("approval_required_role"))
    if not can:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=can_reason)

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
    await audit_write(
        db,
        workspace_id=user.workspace_id,
        actor_type=ActorType.USER,
        actor_id=user.email,
        actor_role=user.role,
        action="recommendation.rejected",
        resource_type="recommendation",
        resource_id=rec_id,
        result=ActionResult.SUCCESS,
        metadata={"reason": reason[:300]} if reason else None,
    )
    doc = await db[col.RECOMMENDATIONS].find_one({"_id": obj_id})
    return _serialize(doc) if doc else {"id": rec_id, "status": "rechazada"}
