"""API config · panel de inteligencia de queries y descubrimiento (Build config).

Endpoints:
- /api/v1/config/queries      · CRUD de watch_queries (CEO)
- /api/v1/config/categories   · catálogo + activar/desactivar
- /api/v1/config/suggestions  · sugerencias del DiscoveryAgent · accept/dismiss
"""
from __future__ import annotations

import contextlib
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from argos.auth.deps import require_role
from argos.auth.schemas import UserOut
from argos.db import collections as col
from argos.db.events import publish_category_requested
from argos.db.mongo import get_database, get_mongo_client
from argos.services.audit import ActionResult, ActorType, audit_write

router = APIRouter(prefix="/api/v1/config", tags=["config"])

QueryStatus = Literal["active", "paused"]
QueryOrigin = Literal["manual", "suggested", "auto_discovered"]
SuggestionStatus = Literal["pending", "accepted", "dismissed"]
SignalType = Literal["trending", "rising", "liquidating", "disappearing"]


def _ensure_mongo() -> None:
    if get_mongo_client() is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB no conectado",
        )


def _parse_oid(s: str) -> ObjectId:
    try:
        return ObjectId(s)
    except InvalidId as exc:
        raise HTTPException(status_code=400, detail="ID inválido") from exc


# ─── Schemas ─────────────────────────────────────────────────────────────


class WatchQueryIn(BaseModel):
    query: str = Field(min_length=2, max_length=200)
    category: str | None = Field(default=None, max_length=80)
    source: str = Field(default="all", pattern=r"^(all|meli|fb_marketplace)$")
    priority: int = Field(default=1, ge=1, le=10)


class WatchQueryPatch(BaseModel):
    query: str | None = Field(default=None, min_length=2, max_length=200)
    category: str | None = Field(default=None, max_length=80)
    status: QueryStatus | None = None
    priority: int | None = Field(default=None, ge=1, le=10)


def _serialize_query(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "query": doc.get("query", ""),
        "category": doc.get("category"),
        "origin": doc.get("origin", "manual"),
        "status": doc.get("status", "active"),
        "priority": int(doc.get("priority") or 1),
        "source": doc.get("source", "all"),
        "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
    }


def _serialize_category(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "slug": doc.get("slug", ""),
        "label": doc.get("label", ""),
        "active": bool(doc.get("active", False)),
    }


def _serialize_suggestion(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "term": doc.get("term", ""),
        "category": doc.get("category", ""),
        "signal_type": doc.get("signal_type", ""),
        "confidence": float(doc.get("confidence") or 0),
        "evidence": doc.get("evidence") or {},
        "date": doc.get("date", ""),
        "status": doc.get("status", "pending"),
    }


# ─── Queries CRUD ────────────────────────────────────────────────────────


@router.get("/queries")
async def list_queries(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
    status_filter: Annotated[QueryStatus | None, Query(alias="status")] = None,
    origin: Annotated[QueryOrigin | None, Query()] = None,
    category: Annotated[str | None, Query(max_length=80)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[dict[str, Any]]:
    _ensure_mongo()
    db = get_database()
    q: dict[str, Any] = {"workspace_id": user.workspace_id}
    if status_filter:
        q["status"] = status_filter
    if origin:
        q["origin"] = origin
    if category:
        q["category"] = category
    cursor = db[col.WATCH_QUERIES].find(q).sort([("priority", -1), ("created_at", -1)]).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_serialize_query(d) for d in docs]


@router.post("/queries", status_code=201)
async def create_query(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
    body: WatchQueryIn,
) -> dict[str, Any]:
    _ensure_mongo()
    db = get_database()
    now = datetime.now(tz=UTC)
    doc = {
        "workspace_id": user.workspace_id,
        "query": body.query.strip(),
        "category": body.category,
        "source": body.source,
        "origin": "manual",
        "status": "active",
        "activa": True,           # legacy compat (Scout)
        "priority": body.priority,
        "prioridad": body.priority,  # legacy compat
        "created_at": now,
        "updated_at": now,
    }
    try:
        result = await db[col.WATCH_QUERIES].insert_one(doc)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=409, detail=f"Query duplicada o inválida: {exc}") from exc
    saved = await db[col.WATCH_QUERIES].find_one({"_id": result.inserted_id})
    await audit_write(
        db,
        workspace_id=user.workspace_id,
        actor_type=ActorType.USER,
        actor_id=user.email,
        actor_role=user.role,
        action="config.watch_query.created",
        resource_type="watch_query",
        resource_id=str(result.inserted_id),
        result=ActionResult.SUCCESS,
        metadata={"query": body.query.strip()[:200], "category": body.category, "source": body.source},
    )
    return _serialize_query(saved or doc)


@router.patch("/queries/{qid}")
async def patch_query(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
    qid: str,
    body: WatchQueryPatch,
) -> dict[str, Any]:
    _ensure_mongo()
    db = get_database()
    oid = _parse_oid(qid)
    set_fields: dict[str, Any] = {"updated_at": datetime.now(tz=UTC)}
    if body.query is not None:
        set_fields["query"] = body.query.strip()
    if body.category is not None:
        set_fields["category"] = body.category
    if body.status is not None:
        set_fields["status"] = body.status
        set_fields["activa"] = body.status == "active"  # legacy sync
    if body.priority is not None:
        set_fields["priority"] = body.priority
        set_fields["prioridad"] = body.priority

    result = await db[col.WATCH_QUERIES].update_one(
        {"_id": oid, "workspace_id": user.workspace_id},
        {"$set": set_fields},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Query no encontrada")
    doc = await db[col.WATCH_QUERIES].find_one({"_id": oid})
    await audit_write(
        db,
        workspace_id=user.workspace_id,
        actor_type=ActorType.USER,
        actor_id=user.email,
        actor_role=user.role,
        action="config.watch_query.updated",
        resource_type="watch_query",
        resource_id=qid,
        result=ActionResult.SUCCESS,
        metadata={"changes": {k: v for k, v in set_fields.items() if k != "updated_at"}},
    )
    return _serialize_query(doc or {})


@router.delete("/queries/{qid}", status_code=204)
async def delete_query(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
    qid: str,
) -> None:
    _ensure_mongo()
    db = get_database()
    oid = _parse_oid(qid)
    result = await db[col.WATCH_QUERIES].delete_one(
        {"_id": oid, "workspace_id": user.workspace_id}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Query no encontrada")
    await audit_write(
        db,
        workspace_id=user.workspace_id,
        actor_type=ActorType.USER,
        actor_id=user.email,
        actor_role=user.role,
        action="config.watch_query.deleted",
        resource_type="watch_query",
        resource_id=qid,
        result=ActionResult.SUCCESS,
    )


# ─── Categories ──────────────────────────────────────────────────────────


@router.get("/categories")
async def list_categories(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
) -> list[dict[str, Any]]:
    _ensure_mongo()
    db = get_database()
    cursor = db[col.CATEGORIES].find({"workspace_id": user.workspace_id}).sort("slug", 1)
    docs = await cursor.to_list(length=100)
    return [_serialize_category(d) for d in docs]


class CategoryPatch(BaseModel):
    active: bool


@router.patch("/categories/{slug}")
async def patch_category(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
    slug: str,
    body: CategoryPatch,
) -> dict[str, Any]:
    _ensure_mongo()
    db = get_database()
    result = await db[col.CATEGORIES].update_one(
        {"workspace_id": user.workspace_id, "slug": slug},
        {"$set": {"active": body.active, "updated_at": datetime.now(tz=UTC)}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    doc = await db[col.CATEGORIES].find_one({"workspace_id": user.workspace_id, "slug": slug})
    await audit_write(
        db,
        workspace_id=user.workspace_id,
        actor_type=ActorType.USER,
        actor_id=user.email,
        actor_role=user.role,
        action="config.category.toggled",
        resource_type="category",
        resource_id=slug,
        result=ActionResult.SUCCESS,
        metadata={"active": body.active},
    )
    return _serialize_category(doc or {})


class CategoryRequest(BaseModel):
    label: str = Field(min_length=2, max_length=80)
    note: str = Field(default="", max_length=300)


@router.post("/categories/request", status_code=202)
async def request_category(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
    body: CategoryRequest,
) -> dict[str, Any]:
    """No crea categoría · solo emite evento al bus para que el equipo de ARGOS la habilite."""
    _ensure_mongo()
    db = get_database()
    await publish_category_requested(
        db,
        workspace_id=user.workspace_id,
        requested_by=user.email,
        label=body.label,
        note=body.note,
    )
    await audit_write(
        db,
        workspace_id=user.workspace_id,
        actor_type=ActorType.USER,
        actor_id=user.email,
        actor_role=user.role,
        action="config.category.requested",
        result=ActionResult.SUCCESS,
        metadata={"label": body.label, "note": body.note[:300]},
    )
    return {"accepted": True, "label": body.label}


# ─── Suggestions ─────────────────────────────────────────────────────────


@router.get("/suggestions")
async def list_suggestions(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
    category: Annotated[str | None, Query(max_length=80)] = None,
    status_filter: Annotated[SuggestionStatus | None, Query(alias="status")] = None,
    signal_type: Annotated[SignalType | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict[str, Any]]:
    _ensure_mongo()
    db = get_database()
    q: dict[str, Any] = {"workspace_id": user.workspace_id}
    if category:
        q["category"] = category
    if status_filter:
        q["status"] = status_filter
    if signal_type:
        q["signal_type"] = signal_type
    cursor = (
        db[col.DISCOVERY_SUGGESTIONS]
        .find(q)
        .sort([("status", 1), ("confidence", -1), ("date", -1)])
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    return [_serialize_suggestion(d) for d in docs]


@router.post("/suggestions/{sid}/accept")
async def accept_suggestion(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
    sid: str,
    source: Annotated[str, Body(embed=True)] = "all",
) -> dict[str, Any]:
    """Acepta sugerencia → crea watch_query con origin='suggested' y marca status='accepted'."""
    _ensure_mongo()
    db = get_database()
    oid = _parse_oid(sid)
    sugg = await db[col.DISCOVERY_SUGGESTIONS].find_one(
        {"_id": oid, "workspace_id": user.workspace_id, "status": "pending"}
    )
    if sugg is None:
        raise HTTPException(status_code=404, detail="Sugerencia no encontrada o ya procesada")

    now = datetime.now(tz=UTC)
    wq_doc = {
        "workspace_id": user.workspace_id,
        "query": sugg["term"],
        "category": sugg.get("category"),
        "source": source if source in {"all", "meli", "fb_marketplace"} else "all",
        "origin": "suggested",
        "status": "active",
        "activa": True,
        "priority": 1,
        "prioridad": 1,
        "suggested_from": str(sugg["_id"]),
        "created_at": now,
        "updated_at": now,
    }
    # Si ya existe por unique (workspace, query), igual marcamos accepted abajo
    with contextlib.suppress(Exception):
        await db[col.WATCH_QUERIES].insert_one(wq_doc)
    await db[col.DISCOVERY_SUGGESTIONS].update_one(
        {"_id": oid},
        {"$set": {"status": "accepted", "accepted_by": user.email, "accepted_at": now}},
    )
    return {"accepted": True, "term": sugg["term"], "category": sugg.get("category")}


@router.post("/suggestions/{sid}/dismiss")
async def dismiss_suggestion(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
    sid: str,
    reason: Annotated[str, Body(embed=True)] = "",
) -> dict[str, Any]:
    _ensure_mongo()
    db = get_database()
    oid = _parse_oid(sid)
    result = await db[col.DISCOVERY_SUGGESTIONS].update_one(
        {"_id": oid, "workspace_id": user.workspace_id, "status": "pending"},
        {
            "$set": {
                "status": "dismissed",
                "dismissed_by": user.email,
                "dismissed_at": datetime.now(tz=UTC),
                "dismiss_reason": reason[:300],
            }
        },
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Sugerencia no encontrada o ya procesada")
    return {"dismissed": True}
