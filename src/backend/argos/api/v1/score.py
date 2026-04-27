"""API Score Engine · POST /evaluate + GET /solicitudes · Phase 2.

ROG-S4: la narrativa de Claude se persiste con la solicitud · auditable.
ROG-S6: notificación al cliente NO va por email (queda excluido en ARGOS).
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from argos.agents.score.engine import ScoreEngine, ScoreSolicitud
from argos.auth.deps import require_role
from argos.auth.schemas import UserOut
from argos.db import collections as col
from argos.db.mongo import get_database, get_mongo_client

router = APIRouter(prefix="/api/v1/score", tags=["score"])

ProductoEnum = Literal["credito_rdx_leasing", "credito_rodante"]
TipoEmpleoEnum = Literal["empleado", "independiente", "delivery", "mototaxi"]
UsoMotoEnum = Literal["personal", "trabajo", "ambos"]
ScoreCompEnum = Literal["A+", "A", "B", "C", "D", "E"]


def _ensure_mongo() -> None:
    if get_mongo_client() is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB no conectado",
        )


class ScoreSolicitudRequest(BaseModel):
    producto: ProductoEnum
    cedula: str = Field(min_length=4, max_length=20)
    nombre: str = Field(min_length=2, max_length=200)
    ingreso_declarado: float = Field(ge=0)
    gastos_mensuales: float = Field(ge=0)
    tipo_empleo: TipoEmpleoEnum
    uso_moto: UsoMotoEnum
    score_comportamental: ScoreCompEnum | None = None
    monto_solicitado: float = Field(default=0.0, ge=0)

    # Datos de partners (opcional · default usa mocks del Phase 2)
    auco_score: float = Field(default=85.0, ge=0, le=100)
    auco_match: bool = True
    riskseal_fraud: bool = False
    riskseal_score: float = Field(default=0.5, ge=0, le=1)
    palenca_ingreso_verificado: float = Field(default=0.0, ge=0)
    palenca_estabilidad_meses: int = Field(default=0, ge=0)
    mora_activa_cop: float = Field(default=0.0, ge=0)
    document_texts: list[str] = Field(default_factory=list, max_length=4)


def _serialize_doc(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "solicitud_id": doc.get("solicitud_id", ""),
        "producto": doc.get("producto", ""),
        "monto_solicitado": float(doc.get("monto_solicitado") or 0),
        "score_final": int(doc.get("score_final") or 0),
        "score_modelo": float(doc.get("score_modelo") or 0),
        "score_claude": float(doc.get("score_claude") or 0),
        "delta_claude": float(doc.get("delta_claude") or 0),
        "narrativa": doc.get("narrativa", ""),
        "decision": doc.get("decision", ""),
        "regla_dura_aplicada": doc.get("regla_dura_aplicada"),
        "fraude_detectado": bool(doc.get("fraude_detectado", False)),
        "threshold_aplicado": int(doc.get("threshold_aplicado") or 0),
        "engine_version": doc.get("engine_version", ""),
        "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
    }


@router.post("/evaluate")
async def evaluate_solicitud(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
    body: ScoreSolicitudRequest,
) -> dict[str, Any]:
    """Evalúa una solicitud · ROG-S3 reglas duras → XGBoost → Claude → decisión."""
    _ensure_mongo()
    db = get_database()
    solicitud_id = f"SCR-ARGOS-{datetime.now(tz=UTC).strftime('%Y%m%d-%H%M%S')}-{body.cedula[-4:]}"

    sol = ScoreSolicitud(
        solicitud_id=solicitud_id,
        producto=body.producto,
        cedula=body.cedula,
        nombre=body.nombre,
        ingreso_declarado=body.ingreso_declarado,
        gastos_mensuales=body.gastos_mensuales,
        tipo_empleo=body.tipo_empleo,
        uso_moto=body.uso_moto,
        score_comportamental=body.score_comportamental,
        monto_solicitado=body.monto_solicitado,
        auco_score=body.auco_score,
        auco_match=body.auco_match,
        riskseal_fraud=body.riskseal_fraud,
        riskseal_score=body.riskseal_score,
        palenca_ingreso_verificado=body.palenca_ingreso_verificado,
        palenca_estabilidad_meses=body.palenca_estabilidad_meses,
        mora_activa_cop=body.mora_activa_cop,
        document_texts=body.document_texts,
    )
    engine = ScoreEngine()
    result = await engine.evaluate(sol, db=db, workspace_id=user.workspace_id)

    return {
        "solicitud_id": result.solicitud_id,
        "producto": result.producto,
        "score_final": result.score_final,
        "score_modelo": result.score_modelo,
        "score_claude": result.score_claude,
        "delta_claude": result.delta_claude,
        "narrativa": result.narrativa,
        "decision": result.decision,
        "regla_dura_aplicada": result.regla_dura_aplicada,
        "fraude_detectado": result.fraude_detectado,
        "threshold_aplicado": result.threshold_aplicado,
        "engine_version": result.engine_version,
    }


@router.get("/solicitudes")
async def list_solicitudes(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
    decision: Annotated[
        Literal["aprobado", "rechazado", "rechazado_regla_dura", "revision_manual"] | None,
        Query(),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[dict[str, Any]]:
    _ensure_mongo()
    db = get_database()
    q: dict[str, Any] = {"workspace_id": user.workspace_id}
    if decision:
        q["decision"] = decision
    cursor = (
        db[col.SCORING_SOLICITUDES]
        .find(q)
        .sort("created_at", -1)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    return [_serialize_doc(d) for d in docs]
