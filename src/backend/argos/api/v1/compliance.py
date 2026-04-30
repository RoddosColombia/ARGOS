"""API Compliance Officer · envelope CRUD + validate (Build 2.5.4 · ROG-A2 + ROG-A10).

Endpoints:
- GET  /api/v1/compliance/envelope                · listado · cualquier role autenticado
- GET  /api/v1/compliance/envelope/{action_type}  · lectura específica
- POST /api/v1/compliance/envelope                · CREAR/UPDATE · solo CEO (Plano 3)
- POST /api/v1/compliance/validate                · valida una acción · cualquier agente

Toda mutación queda en `audit_log` (ROG-A12). Validación queda en logs (no audit
porque sería ruido masivo · cada Plano 1 ejecutado va a tener su propio audit
desde el agente que lo ejecutó).
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from argos.agents.compliance_officer import (
    ComplianceOfficer,
    ComplianceOfficerError,
    serialize_envelope_doc,
)
from argos.auth.deps import require_role
from argos.auth.schemas import UserOut
from argos.db.mongo import get_database, get_mongo_client
from argos.services.audit import ActionResult, ActorType, audit_write

router = APIRouter(prefix="/api/v1/compliance", tags=["compliance"])


def _ensure_mongo() -> None:
    if get_mongo_client() is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB no conectado · operación compliance no disponible",
        )


def _audit_db():
    if get_mongo_client() is None:
        return None
    return get_database()


def _client_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    return request.client.host


# ─── Schemas ─────────────────────────────────────────────────────────────


class EnvelopeUpsertBody(BaseModel):
    action_type: str = Field(min_length=3, max_length=80, pattern=r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_.]*$")
    plano: int = Field(ge=1, le=3)
    plano_if_outside: int = Field(ge=1, le=3)
    params_schema: dict[str, str] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)
    description: str = Field(min_length=1, max_length=400)


class ValidateBody(BaseModel):
    action_type: str = Field(min_length=3, max_length=80)
    params: dict[str, Any] = Field(default_factory=dict)
    requested_by: str = Field(default="sistema", max_length=200)


# ─── Endpoints ───────────────────────────────────────────────────────────


@router.get("/envelope")
async def list_envelopes(
    user: Annotated[UserOut, Depends(require_role("ceo", "cgo", "analista", "sistema"))],
) -> list[dict[str, Any]]:
    """Listado de envelopes activos del workspace · CEO + CGO ven lo mismo (ROG-G1)."""
    _ensure_mongo()
    officer = ComplianceOfficer(get_database())
    docs = await officer.list_envelopes(workspace_id=user.workspace_id)
    return [serialize_envelope_doc(d) for d in docs]


@router.get("/envelope/{action_type}")
async def get_envelope(
    user: Annotated[UserOut, Depends(require_role("ceo", "cgo", "analista", "sistema"))],
    action_type: Annotated[str, Path(min_length=3, max_length=80)],
) -> dict[str, Any]:
    """Lectura de un envelope específico."""
    _ensure_mongo()
    officer = ComplianceOfficer(get_database())
    doc = await officer.get_envelope(
        workspace_id=user.workspace_id, action_type=action_type,
    )
    if doc is None:
        raise HTTPException(
            status_code=404,
            detail=f"No hay envelope activo para action_type={action_type!r}",
        )
    return serialize_envelope_doc(doc)


@router.post("/envelope", status_code=200)
async def upsert_envelope(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
    request: Request,
    body: EnvelopeUpsertBody,
) -> dict[str, Any]:
    """Crear o actualizar envelope · solo CEO (Plano 3 enforzado por role check).

    Cualquier cambio aquí es decisión estratégica · queda auditado.
    """
    _ensure_mongo()
    officer = ComplianceOfficer(get_database())
    try:
        doc = await officer.upsert_envelope(
            workspace_id=user.workspace_id,
            action_type=body.action_type,
            plano=body.plano,
            plano_if_outside=body.plano_if_outside,
            params_schema=body.params_schema,
            constraints=body.constraints,
            description=body.description,
            approved_by=user.email,
        )
    except ComplianceOfficerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await audit_write(
        _audit_db(),
        workspace_id=user.workspace_id,
        actor_type=ActorType.USER,
        actor_id=user.email,
        actor_role=user.role,
        action="compliance.envelope.upserted",
        resource_type="compliance_envelope",
        resource_id=body.action_type,
        result=ActionResult.SUCCESS,
        metadata={
            "plano": body.plano,
            "plano_if_outside": body.plano_if_outside,
            "constraints": body.constraints,
        },
        ip_address=_client_ip(request),
    )
    return serialize_envelope_doc(doc)


@router.post("/validate")
async def validate_action(
    user: Annotated[UserOut, Depends(require_role("ceo", "cgo", "analista", "sistema"))],
    body: ValidateBody,
) -> dict[str, Any]:
    """Valida una acción contra el envelope vigente · cualquier agente puede llamar.

    Devuelve `{allowed, plano_required, reason, action_type, envelope_present}`.
    El caller decide qué hacer según el plano (auto-execute, escalate-to-CGO, escalate-to-CEO).
    """
    _ensure_mongo()
    officer = ComplianceOfficer(get_database())
    try:
        decision = await officer.validate_action(
            workspace_id=user.workspace_id,
            action_type=body.action_type,
            params=body.params,
            requested_by=body.requested_by or user.email,
        )
    except ComplianceOfficerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "allowed": decision.allowed,
        "plano_required": decision.plano_required,
        "reason": decision.reason,
        "action_type": decision.action_type,
        "envelope_present": decision.envelope_present,
    }
