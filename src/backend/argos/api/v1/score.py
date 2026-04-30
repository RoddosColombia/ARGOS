"""API Score Engine · Phase 2 · ARGOS pass-through al motor externo de Iván.

- POST /api/v1/score/evaluate     → forward a SCORE_ENGINE_API_URL/v1/evaluate
- GET  /api/v1/score/solicitudes  → lee scoring_solicitudes desde RODDOS_MONGODB_URI
- GET  /api/v1/score/config       → expone URL del Score Engine (para banner UI)

ARGOS NO ejecuta scores · NO aplica reglas duras · NO llama Claude.
La auditoría (ROG-S4) y el versionado del modelo (ROG-S5) viven en el repo de Iván,
PERO ARGOS persiste audit local lado-Argos de cada llamada (Build 2.5.2 · ROG-A12).
"""
from __future__ import annotations

import hashlib
import json
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from argos.agents.score.client import ScoreEngineClient, ScoreEngineError
from argos.agents.score.reader import ScoreReader
from argos.auth.deps import require_role
from argos.auth.schemas import UserOut
from argos.config import get_settings
from argos.db.mongo import get_database, get_mongo_client
from argos.services.audit import ActionResult, ActorType, audit_write

router = APIRouter(prefix="/api/v1/score", tags=["score"])


def _audit_db():
    """Devuelve el DB para audit_write o None si Mongo no está configurado.

    `audit_write` skipea silenciosamente con db=None · permite que el endpoint
    siga sirviendo si solo está disponible RODDOS_MONGODB_URI sin MONGODB_URI.
    """
    if get_mongo_client() is None:
        return None
    return get_database()


def _payload_hash(payload: dict[str, Any]) -> str:
    """Hash determinístico del payload sin persistir PII (ROG-A9)."""
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


@router.get("/config")
async def score_config(
    _user: Annotated[UserOut, Depends(require_role("ceo"))],
) -> dict[str, Any]:
    """Endpoint informativo para el banner del frontend."""
    s = get_settings()
    return {
        "score_engine_api_url": s.score_engine_api_url or None,
        "roddos_mongodb_configured": bool(s.roddos_mongodb_uri),
    }


@router.post("/evaluate")
async def evaluate_solicitud(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
    payload: Annotated[dict[str, Any], Body(description="Payload del Score Engine externo")],
) -> dict[str, Any]:
    """Pass-through: reenvía el payload al Score Engine de Iván y devuelve la respuesta cruda.

    Audit local (ROG-S4 · ROG-A12): cada llamada queda en `audit_log` con hash del
    payload (sin PII), decision recibida, engine_version.
    """
    db = _audit_db()
    payload_hash = _payload_hash(payload)
    client = ScoreEngineClient()
    try:
        resp = await client.evaluate(payload)
    except ScoreEngineError as exc:
        await audit_write(
            db,
            workspace_id=user.workspace_id,
            actor_type=ActorType.USER,
            actor_id=user.email,
            actor_role=user.role,
            action="score.evaluate.failed",
            result=ActionResult.FAILURE,
            metadata={
                "payload_hash": payload_hash,
                "http_status": exc.status,
                "error": exc.message[:200],
            },
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Score Engine error · {exc.status}: {exc.message[:200]}",
        ) from exc

    body = dict(resp.raw)
    # Garantizar campos canónicos en el response (incluso si el upstream no los puso)
    body.setdefault("decision", resp.decision)
    body.setdefault("score_final", resp.score_final)
    body.setdefault("solicitud_id", resp.solicitud_id)

    await audit_write(
        db,
        workspace_id=user.workspace_id,
        actor_type=ActorType.USER,
        actor_id=user.email,
        actor_role=user.role,
        action="score.evaluate.requested",
        resource_type="scoring_solicitud",
        resource_id=resp.solicitud_id or None,
        result=ActionResult.SUCCESS,
        metadata={
            "payload_hash": payload_hash,
            "decision": resp.decision,
            "score_final": resp.score_final,
            "engine_version": resp.raw.get("engine_version"),
        },
    )

    return body


@router.get("/solicitudes")
async def list_solicitudes(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
    decision: Annotated[str | None, Query(max_length=40)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[dict[str, Any]]:
    """Lee scoring_solicitudes desde RODDOS_MONGODB_URI (DB compartida con Iván).

    Si RODDOS_MONGODB_URI no está configurado, devuelve [] (skip silencioso).
    """
    reader = ScoreReader()
    try:
        records = await reader.get_recent(
            workspace_id=user.workspace_id, limit=limit, decision=decision,
        )
    finally:
        await reader.close()
    return [
        {
            "id": r.solicitud_id,
            "solicitud_id": r.solicitud_id,
            "producto": r.producto,
            "score_final": r.score_final,
            "decision": r.decision,
            "nombre": r.nombre,
            "monto_solicitado": r.monto_solicitado,
            "narrativa": r.narrativa,
            "regla_dura_aplicada": r.regla_dura_aplicada,
            "engine_version": r.engine_version,
            "created_at": r.created_at,
        }
        for r in records
    ]
