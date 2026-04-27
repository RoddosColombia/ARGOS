"""Capa 1 · scorecard ponderado · Phase 2.

DT-020: cuando la cartera tenga ≥500 registros con outcome (cuotas pagadas/vencidas
en SISMO loanbook), entrenar un XGBoost real con joblib + hash · ROG-S5. Hasta
entonces, este scorer manual ponderado emula la salida de un XGBoost en rango
[0.0, 1.0] usando pesos hardcodeados de dominio motorizado colombiano.

ROG-S1: pesos y partners idénticos al motor del admin de www.roddos.com (Build 20).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger("argos.agents.score.xgboost")

ScoreComportamental = Literal["A+", "A", "B", "C", "D", "E"]
TipoEmpleo = Literal["empleado", "independiente", "delivery", "mototaxi"]
Producto = Literal["credito_rdx_leasing", "credito_rodante"]
UsoMoto = Literal["personal", "trabajo", "ambos"]


SCORE_COMPORTAMENTAL_MAP: dict[str, float] = {
    "A+": 1.00,
    "A":  0.85,
    "B":  0.70,
    "C":  0.50,
    "D":  0.30,
    "E":  0.10,
}


def score_comportamental_to_float(s: str | None) -> float:
    if not s:
        return 0.5  # cliente nuevo · neutral
    return SCORE_COMPORTAMENTAL_MAP.get(s, 0.5)


# Pesos del scorecard ponderado · suma = 1.0
WEIGHTS: dict[str, float] = {
    "score_externo": 0.30,        # RiskSeal o Palenca señal externa
    "capacidad_pago": 0.25,       # 1 - DTI (debt-to-income)
    "estabilidad_laboral": 0.15,  # estabilidad_meses normalizado
    "score_comportamental": 0.20, # historial RODDOS si aplica
    "validacion_biometrica": 0.10,# AUCO score / 100
}


@dataclass
class Scorecard:
    """Insumo del XGBoostScorer · todos los features normalizados a [0.0, 1.0]."""
    score_externo: float        # RiskSeal risk_score O Palenca derivado
    capacidad_pago: float       # 1 - dti, ya capeado a [0,1]
    estabilidad_laboral: float  # estabilidad_meses / 24, capped 1.0
    score_comportamental: float # ver SCORE_COMPORTAMENTAL_MAP
    validacion_biometrica: float# AUCO score / 100

    # Categóricos · NO entran en el cálculo manual pero quedan disponibles para
    # el XGBoost real cuando se entrene. Sirven también para el prompt de Claude.
    producto: Producto = "credito_rodante"
    tipo_empleo: TipoEmpleo = "empleado"
    uso_moto: UsoMoto = "personal"


class XGBoostScorer:
    """Stateless · `score()` retorna float en [0.0, 1.0].

    Build 2.0 (Phase 2): scorecard manual ponderado.
    Build 5+: cargar joblib del XGBoost entrenado · ROG-S5 (hash en argos_events).
    """

    def __init__(self, model_version: str = "v0.1.0-manual") -> None:
        self.model_version = model_version

    def score(self, sc: Scorecard) -> float:
        """Producto-punto pesos·features · clamp a [0,1]."""
        raw = (
            WEIGHTS["score_externo"] * sc.score_externo
            + WEIGHTS["capacidad_pago"] * sc.capacidad_pago
            + WEIGHTS["estabilidad_laboral"] * sc.estabilidad_laboral
            + WEIGHTS["score_comportamental"] * sc.score_comportamental
            + WEIGHTS["validacion_biometrica"] * sc.validacion_biometrica
        )
        clamped = max(0.0, min(1.0, raw))
        logger.debug("xgboost_scored", extra={
            "model_version": self.model_version,
            "score": clamped,
        })
        return clamped
