"""API contacts · opt-in / opt-out / status (Build 2.5.3 · ROG-W1 preventivo).

Endpoints:
- POST /api/v1/contacts/{phone_number}/opt-in
- POST /api/v1/contacts/{phone_number}/opt-out
- GET  /api/v1/contacts/{phone_number}/opt-status
- GET  /api/v1/contacts                          (listado paginado)

Toda mutación queda en `audit_log` (Build 2.5.2 · ROG-A12). El gate
`can_send_proactive` del módulo `argos.services.opt_in` debe llamarse desde
TODO punto que dispare un mensaje proactivo (Phase 3+).
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from pydantic import BaseModel, Field

from argos.auth.deps import require_role
from argos.auth.schemas import UserOut
from argos.db import collections as col
from argos.db.mongo import get_database, get_mongo_client
from argos.services.audit import ActionResult, ActorType, audit_write
from argos.services.opt_in import (
    OptInValidationError,
    get_opt_status,
    record_opt_in,
    record_opt_out,
)

router = APIRouter(prefix="/api/v1/contacts", tags=["contacts"])


def _ensure_mongo() -> None:
    if get_mongo_client() is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB no conectado · operación contacts no disponible",
        )


def _audit_db():
    """Devuelve la database o None para que audit_write haga skip silencioso."""
    if get_mongo_client() is None:
        return None
    return get_database()


def _client_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    return request.client.host


# ─── Schemas ─────────────────────────────────────────────────────────────


class OptInBody(BaseModel):
    type: Literal["marketing", "utility"]
    channel: Literal["sms", "web", "whatsapp_inbound", "sales_call", "qr_empaque"]
    consent_text_version: str = Field(min_length=1, max_length=80)
    captured_by: str = Field(min_length=1, max_length=200)
    name: str | None = Field(default=None, max_length=200)


class OptOutBody(BaseModel):
    type: Literal["marketing", "utility"]
    captured_by: str = Field(min_length=1, max_length=200)
    reason: str | None = Field(default=None, max_length=200)


def _serialize_contact(doc: dict[str, Any] | None, *, include_history: bool = False) -> dict[str, Any]:
    if not doc:
        return {}

    def _block(field: str) -> dict[str, Any] | None:
        block = doc.get(field)
        if not block:
            return None
        out = {
            "status": block.get("status"),
            "captured_at": block["captured_at"].isoformat() if block.get("captured_at") else None,
            "channel": block.get("channel"),
            "consent_text_version": block.get("consent_text_version"),
            "captured_by": block.get("captured_by"),
        }
        if block.get("opted_out_at"):
            out["opted_out_at"] = block["opted_out_at"].isoformat()
            out["opted_out_by"] = block.get("opted_out_by")
        if include_history:
            history = block.get("history") or []
            out["history"] = [
                {
                    "status": h.get("status"),
                    "at": h["at"].isoformat() if h.get("at") else None,
                    "channel": h.get("channel"),
                    "captured_by": h.get("captured_by"),
                    "reason": h.get("reason"),
                }
                for h in history
            ]
        return out

    return {
        "id": str(doc.get("_id")) if doc.get("_id") else None,
        "phone_number": doc.get("phone_number"),
        "name": doc.get("name"),
        "customer_id_sismo": doc.get("customer_id_sismo"),
        "opt_in_marketing": _block("opt_in_marketing"),
        "opt_in_utility": _block("opt_in_utility"),
        "last_message_at": doc["last_message_at"].isoformat() if doc.get("last_message_at") else None,
        "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
        "updated_at": doc["updated_at"].isoformat() if doc.get("updated_at") else None,
    }


# ─── Endpoints ───────────────────────────────────────────────────────────


@router.post("/{phone_number}/opt-in", status_code=201)
async def opt_in_contact(
    user: Annotated[UserOut, Depends(require_role("ceo", "cgo", "analista", "sistema"))],
    request: Request,
    phone_number: Annotated[str, Path(min_length=8, max_length=20)],
    body: OptInBody,
) -> dict[str, Any]:
    """Registra opt-in para un phone · upsert con audit trail · cumple ROG-W1."""
    _ensure_mongo()
    db = get_database()
    try:
        contact = await record_opt_in(
            db,
            workspace_id=user.workspace_id,
            phone_number=phone_number,
            opt_type=body.type,
            channel=body.channel,
            consent_text_version=body.consent_text_version,
            captured_by=body.captured_by,
            name=body.name,
        )
    except OptInValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await audit_write(
        _audit_db(),
        workspace_id=user.workspace_id,
        actor_type=ActorType.USER,
        actor_id=user.email,
        actor_role=user.role,
        action=f"contacts.opt_in.{body.type}",
        resource_type="contact",
        resource_id=phone_number,
        result=ActionResult.SUCCESS,
        metadata={
            "channel": body.channel,
            "consent_text_version": body.consent_text_version,
            "captured_by": body.captured_by,
        },
        ip_address=_client_ip(request),
    )
    return _serialize_contact(contact)


@router.post("/{phone_number}/opt-out", status_code=200)
async def opt_out_contact(
    user: Annotated[UserOut, Depends(require_role("ceo", "cgo", "analista", "sistema"))],
    request: Request,
    phone_number: Annotated[str, Path(min_length=8, max_length=20)],
    body: OptOutBody,
) -> dict[str, Any]:
    """Registra opt-out · cambia status a opted_out · preserva history."""
    _ensure_mongo()
    db = get_database()
    try:
        contact = await record_opt_out(
            db,
            workspace_id=user.workspace_id,
            phone_number=phone_number,
            opt_type=body.type,
            captured_by=body.captured_by,
            reason=body.reason,
        )
    except OptInValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if contact is None:
        # contact no existe · NO se crea por opt-out · 404 sigue siendo respuesta válida
        await audit_write(
            _audit_db(),
            workspace_id=user.workspace_id,
            actor_type=ActorType.USER,
            actor_id=user.email,
            actor_role=user.role,
            action=f"contacts.opt_out.{body.type}.no_contact",
            resource_type="contact",
            resource_id=phone_number,
            result=ActionResult.FAILURE,
            metadata={"reason": "contact_not_found"},
            ip_address=_client_ip(request),
        )
        raise HTTPException(status_code=404, detail="Contacto no encontrado · opt-out no aplicable")

    await audit_write(
        _audit_db(),
        workspace_id=user.workspace_id,
        actor_type=ActorType.USER,
        actor_id=user.email,
        actor_role=user.role,
        action=f"contacts.opt_out.{body.type}",
        resource_type="contact",
        resource_id=phone_number,
        result=ActionResult.SUCCESS,
        metadata={
            "captured_by": body.captured_by,
            "reason": (body.reason or "")[:200],
        },
        ip_address=_client_ip(request),
    )
    return _serialize_contact(contact)


@router.get("/{phone_number}/opt-status")
async def opt_status_contact(
    user: Annotated[UserOut, Depends(require_role("ceo", "cgo", "analista", "sistema"))],
    phone_number: Annotated[str, Path(min_length=8, max_length=20)],
) -> dict[str, Any]:
    """Lectura del estado de opt-in vigente para un phone (no audita lecturas)."""
    _ensure_mongo()
    db = get_database()
    try:
        contact = await get_opt_status(
            db,
            workspace_id=user.workspace_id,
            phone_number=phone_number,
        )
    except OptInValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if contact is None:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")
    return _serialize_contact(contact, include_history=True)


@router.get("")
async def list_contacts(
    user: Annotated[UserOut, Depends(require_role("ceo", "cgo", "analista"))],
    opt_in_marketing: Annotated[bool | None, Query()] = None,
    opt_in_utility: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[dict[str, Any]]:
    """Listado paginado de contacts del workspace · filtros opcionales por opt-in vigente."""
    _ensure_mongo()
    db = get_database()
    q: dict[str, Any] = {"workspace_id": user.workspace_id}
    if opt_in_marketing is not None:
        q["opt_in_marketing.status"] = "opted_in" if opt_in_marketing else {"$ne": "opted_in"}
    if opt_in_utility is not None:
        q["opt_in_utility.status"] = "opted_in" if opt_in_utility else {"$ne": "opted_in"}
    cursor = (
        db[col.CONTACTS]
        .find(q)
        .sort([("updated_at", -1), ("created_at", -1)])
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    return [_serialize_contact(d) for d in docs]
