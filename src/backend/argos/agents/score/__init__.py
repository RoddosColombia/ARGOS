"""Score Engine · Phase 2 · clon interno del motor del admin web (ROG-S1).

Capa 1 (XGBoostScorer): scorecard ponderado · cuando cartera ≥500 entrenar XGBoost real.
Capa 2 (ClaudeScorer): coherencia KYC + detección de fraude + ajuste cualitativo ±0.15.
Orquestador: ScoreEngine · reglas duras (ROG-S3) → si no, score combinado → decisión.
"""
from argos.agents.score.claude_scorer import ClaudeScorer, ClaudeScoreResult
from argos.agents.score.engine import ScoreEngine, ScoreResult, ScoreSolicitud
from argos.agents.score.xgboost_scorer import (
    Scorecard,
    XGBoostScorer,
    score_comportamental_to_float,
)

__all__ = [
    "ScoreEngine", "ScoreResult", "ScoreSolicitud",
    "Scorecard", "XGBoostScorer", "score_comportamental_to_float",
    "ClaudeScorer", "ClaudeScoreResult",
]
