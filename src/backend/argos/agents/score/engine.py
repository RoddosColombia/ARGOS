"""ScoreEngine · orquestador 2-capas + reglas duras (ROG-S3) · Phase 2.

Pipeline:
1. Reglas duras → si AUCO<70, RiskSeal fraud, mora>3M, DTI>0.60: rechazo inmediato
2. Sino → XGBoostScorer.score(scorecard) → score_modelo ∈ [0,1]
3. → ClaudeScorer.analyze(kyc, docs, partners) → delta ∈ [-0.15, +0.15]
4. score_final = (0.7 * score_modelo + 0.3 * (score_modelo + delta)) * 1000
   simplificado: score_final = (score_modelo + 0.3 * delta) * 1000  · clamped [0, 1000]
5. Decisión por umbral del producto + bypass cliente RODDOS A+/A/B (ROG-S1)
6. Persistencia en scoring_solicitudes + emit `score.evaluated` al bus
7. Versión del engine pineada en metadata del evento (ROG-S5)
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.agents.score.claude_scorer import ClaudeScorer, ClaudeScoreResult
from argos.agents.score.xgboost_scorer import (
    Scorecard,
    XGBoostScorer,
    score_comportamental_to_float,
)
from argos.config import get_settings
from argos.db import collections as col
from argos.db.events import publish_score_evaluated

logger = logging.getLogger("argos.agents.score.engine")

# Reglas duras (ROG-S3)
HARD_RULE_AUCO_MIN = 70.0
HARD_RULE_MORA_MAX_COP = 3_000_000.0
HARD_RULE_DTI_MAX = 0.60

# Pesos de la combinación · `0.7 * modelo + 0.3 * (modelo + delta)` simplifica a
# `modelo + 0.3 * delta` después del álgebra. Mantenido explícito en formula().
MODEL_WEIGHT = 0.7
CLAUDE_WEIGHT = 0.3

# Umbrales por producto · ROG-S1 bypass cliente RODDOS
DECISION_THRESHOLDS: dict[tuple[str, bool], int] = {
    # (producto, es_cliente_roddos_positivo)
    ("credito_rdx_leasing", False): 650,
    ("credito_rdx_leasing", True): 600,   # cliente A+
    ("credito_rodante", False): 500,
    ("credito_rodante", True): 400,        # cliente A+/A/B (bypass flujo F3)
}


@dataclass
class ScoreSolicitud:
    """Insumo del engine · datos crudos antes del scorecard."""
    solicitud_id: str
    producto: str  # credito_rdx_leasing | credito_rodante
    cedula: str
    nombre: str
    ingreso_declarado: float
    gastos_mensuales: float
    tipo_empleo: str
    uso_moto: str
    score_comportamental: str | None = None  # A+/A/B/C/D/E o None si nuevo
    monto_solicitado: float = 0.0

    # Resultados de partners (mock por ahora · Phase 3 cliente real)
    auco_score: float = 85.0
    auco_match: bool = True
    riskseal_fraud: bool = False
    riskseal_score: float = 0.5
    palenca_ingreso_verificado: float = 0.0
    palenca_estabilidad_meses: int = 0
    mora_activa_cop: float = 0.0  # de SISMO loanbook (Phase 4 read real)

    # Documentos opcionales para Claude
    document_texts: list[str] = field(default_factory=list)


@dataclass
class ScoreResult:
    solicitud_id: str
    producto: str
    score_final: int                      # 0-1000
    score_modelo: float                   # 0.0-1.0 (capa 1)
    score_claude: float                   # score_modelo + delta (auditoría)
    delta_claude: float                   # delta crudo de Claude
    narrativa: str
    decision: str                         # aprobado | rechazado | rechazado_regla_dura | revision_manual
    regla_dura_aplicada: str | None
    fraude_detectado: bool
    engine_version: str
    prompt_version: str
    threshold_aplicado: int
    tokens_input: int = 0
    tokens_output: int = 0


class ScoreEngine:
    def __init__(
        self,
        xgboost: XGBoostScorer | None = None,
        claude: ClaudeScorer | None = None,
    ) -> None:
        settings = get_settings()
        self._xgb = xgboost or XGBoostScorer(model_version=settings.score_engine_version)
        self._claude = claude or ClaudeScorer(api_key=settings.anthropic_api_key)
        self._engine_version = settings.score_engine_version

    # ─── Reglas duras (ROG-S3) ────────────────────────────────────────────

    def _check_hard_rules(self, sol: ScoreSolicitud) -> str | None:
        """Devuelve nombre de la regla violada o None."""
        if sol.auco_score < HARD_RULE_AUCO_MIN:
            return f"auco_score<{HARD_RULE_AUCO_MIN}"
        if sol.riskseal_fraud:
            return "riskseal_fraud_flag"
        if sol.mora_activa_cop > HARD_RULE_MORA_MAX_COP:
            return f"mora_activa>{int(HARD_RULE_MORA_MAX_COP)}"
        dti = self._compute_dti(sol)
        if dti > HARD_RULE_DTI_MAX:
            return f"dti>{HARD_RULE_DTI_MAX}"
        return None

    @staticmethod
    def _compute_dti(sol: ScoreSolicitud) -> float:
        """Debt-to-income estimado · usa ingreso Palenca si está, sino el declarado."""
        ingreso = sol.palenca_ingreso_verificado or sol.ingreso_declarado
        if ingreso <= 0:
            return 1.0
        return min(1.0, sol.gastos_mensuales / ingreso)

    # ─── Scorecard ────────────────────────────────────────────────────────

    def _build_scorecard(self, sol: ScoreSolicitud) -> Scorecard:
        dti = self._compute_dti(sol)
        capacidad = max(0.0, 1.0 - dti)
        # Estabilidad: 0 meses → 0, 24+ meses → 1.0
        estabilidad = min(1.0, max(0, sol.palenca_estabilidad_meses) / 24.0)
        score_externo = sol.riskseal_score
        return Scorecard(
            score_externo=score_externo,
            capacidad_pago=capacidad,
            estabilidad_laboral=estabilidad,
            score_comportamental=score_comportamental_to_float(sol.score_comportamental),
            validacion_biometrica=min(1.0, max(0.0, sol.auco_score / 100.0)),
            producto=sol.producto,  # type: ignore[arg-type]
            tipo_empleo=sol.tipo_empleo,  # type: ignore[arg-type]
            uso_moto=sol.uso_moto,  # type: ignore[arg-type]
        )

    # ─── Decisión ─────────────────────────────────────────────────────────

    def _resolve_threshold(self, sol: ScoreSolicitud) -> int:
        """ROG-S1 bypass: cliente RODDOS con A+/A/B reduce el threshold."""
        is_positive_client = sol.score_comportamental in {"A+", "A", "B"}
        # Para credito_rdx_leasing solo bypass aplica a A+
        if sol.producto == "credito_rdx_leasing":
            is_positive_client = sol.score_comportamental == "A+"
        return DECISION_THRESHOLDS.get((sol.producto, is_positive_client), 500)

    def _decide(self, score_final: int, threshold: int, fraude: bool) -> str:
        if fraude:
            return "revision_manual"
        return "aprobado" if score_final >= threshold else "rechazado"

    # ─── Pipeline público ──────────────────────────────────────────────────

    async def evaluate(
        self, sol: ScoreSolicitud, *, db: AsyncIOMotorDatabase | None = None,
        workspace_id: str = "RODDOS",
    ) -> ScoreResult:
        # 1. Reglas duras
        violated = self._check_hard_rules(sol)
        if violated is not None:
            result = ScoreResult(
                solicitud_id=sol.solicitud_id,
                producto=sol.producto,
                score_final=0,
                score_modelo=0.0,
                score_claude=0.0,
                delta_claude=0.0,
                narrativa=f"Rechazo automático por regla dura: {violated} (ROG-S3)",
                decision="rechazado_regla_dura",
                regla_dura_aplicada=violated,
                fraude_detectado=False,
                engine_version=self._engine_version,
                prompt_version="n/a",
                threshold_aplicado=self._resolve_threshold(sol),
            )
            await self._persist_and_emit(db, workspace_id, sol, result)
            return result

        # 2. Capa 1 · XGBoost manual ponderado
        scorecard = self._build_scorecard(sol)
        score_modelo = self._xgb.score(scorecard)

        # 3. Capa 2 · Claude
        kyc = {
            "cedula": sol.cedula[-4:].rjust(len(sol.cedula), "*"),  # privacy: solo últimos 4 dígitos
            "nombre": sol.nombre,
            "producto": sol.producto,
            "ingreso_declarado": sol.ingreso_declarado,
            "gastos_mensuales": sol.gastos_mensuales,
            "tipo_empleo": sol.tipo_empleo,
            "uso_moto": sol.uso_moto,
            "monto_solicitado": sol.monto_solicitado,
            "score_comportamental": sol.score_comportamental,
        }
        partner_data = {
            "auco": {"score": sol.auco_score, "match": sol.auco_match},
            "riskseal": {"fraud_flag": sol.riskseal_fraud, "risk_score": sol.riskseal_score},
            "palenca": {
                "ingreso_verificado": sol.palenca_ingreso_verificado,
                "estabilidad_meses": sol.palenca_estabilidad_meses,
            },
            "mora_activa_cop": sol.mora_activa_cop,
        }
        claude_result: ClaudeScoreResult = await self._claude.analyze(
            kyc, document_texts=sol.document_texts, partner_data=partner_data,
        )

        # 4. Score final · MODEL_WEIGHT * modelo + CLAUDE_WEIGHT * (modelo + delta)
        # Algebraicamente: modelo + CLAUDE_WEIGHT * delta
        score_claude = max(0.0, min(1.0, score_modelo + claude_result.delta))
        combined = MODEL_WEIGHT * score_modelo + CLAUDE_WEIGHT * score_claude
        score_final = max(0, min(1000, int(round(combined * 1000))))

        # 5. Decisión
        threshold = self._resolve_threshold(sol)
        decision = self._decide(score_final, threshold, claude_result.fraude_detectado)

        result = ScoreResult(
            solicitud_id=sol.solicitud_id,
            producto=sol.producto,
            score_final=score_final,
            score_modelo=round(score_modelo, 4),
            score_claude=round(score_claude, 4),
            delta_claude=round(claude_result.delta, 4),
            narrativa=claude_result.narrativa,
            decision=decision,
            regla_dura_aplicada=None,
            fraude_detectado=claude_result.fraude_detectado,
            engine_version=self._engine_version,
            prompt_version=claude_result.prompt_version,
            threshold_aplicado=threshold,
            tokens_input=claude_result.tokens_input,
            tokens_output=claude_result.tokens_output,
        )
        await self._persist_and_emit(db, workspace_id, sol, result)
        return result

    async def _persist_and_emit(
        self,
        db: AsyncIOMotorDatabase | None,
        workspace_id: str,
        sol: ScoreSolicitud,
        result: ScoreResult,
    ) -> None:
        if db is None:
            return
        now = datetime.now(tz=UTC)
        doc: dict[str, Any] = {
            "workspace_id": workspace_id,
            "origen": "argos",
            "solicitud_id": sol.solicitud_id,
            "producto": sol.producto,
            "monto_solicitado": sol.monto_solicitado,
            **{k: v for k, v in asdict(result).items()},
            "kyc": {
                "nombre": sol.nombre,
                "cedula_last4": sol.cedula[-4:],
                "tipo_empleo": sol.tipo_empleo,
                "uso_moto": sol.uso_moto,
                "score_comportamental": sol.score_comportamental,
                "ingreso_declarado": sol.ingreso_declarado,
                "gastos_mensuales": sol.gastos_mensuales,
            },
            "partners": {
                "auco": {"score": sol.auco_score, "match": sol.auco_match},
                "riskseal": {"fraud_flag": sol.riskseal_fraud, "risk_score": sol.riskseal_score},
                "palenca": {
                    "ingreso_verificado": sol.palenca_ingreso_verificado,
                    "estabilidad_meses": sol.palenca_estabilidad_meses,
                },
                "mora_activa_cop": sol.mora_activa_cop,
            },
            "created_at": now,
            "updated_at": now,
        }
        await db[col.SCORING_SOLICITUDES].update_one(
            {"workspace_id": workspace_id, "solicitud_id": sol.solicitud_id},
            {"$set": doc},
            upsert=True,
        )
        await publish_score_evaluated(
            db,
            workspace_id=workspace_id,
            solicitud_id=sol.solicitud_id,
            decision=result.decision,
            score_final=result.score_final,
            engine_version=result.engine_version,
            regla_dura_aplicada=result.regla_dura_aplicada,
        )
        logger.info("score_evaluated", extra={
            "solicitud_id": sol.solicitud_id,
            "decision": result.decision,
            "score_final": result.score_final,
        })
