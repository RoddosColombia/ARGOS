"""Score Engine externo · ARGOS solo lee resultados y expone cliente HTTP.

Corrección arquitectónica 2026-04-27: el motor de scoring es repo independiente
(Iván) que escribe en MongoDB compartido. ARGOS NO ejecuta scores.

- `ScoreReader` · lee scoring_solicitudes desde RODDOS_MONGODB_URI (read-only).
- `ScoreEngineClient` · POST a SCORE_ENGINE_API_URL para que WhatsApp Agent
  dispare evaluaciones · ARGOS es pass-through.
"""
from argos.agents.score.client import ScoreEngineClient, ScoreEngineResponse
from argos.agents.score.reader import ScoreReader, ScoreRecord

__all__ = [
    "ScoreEngineClient",
    "ScoreEngineResponse",
    "ScoreReader",
    "ScoreRecord",
]
