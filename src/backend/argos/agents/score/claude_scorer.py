"""Capa 2 · ClaudeScorer · ajuste cualitativo + narrativa auditable (ROG-S4).

Sonnet 4.6 lee KYC + textos de documentos + resultados de partners y devuelve:
- delta · ajuste en [-0.15, +0.15] al score de la Capa 1
- narrativa · explicación auditable (texto plano, persiste en scoring_solicitudes)
- fraude_detectado · bandera para escalar a revisión manual
"""
from __future__ import annotations

import contextlib
import json
import logging
from dataclasses import dataclass
from typing import Any

from argos.agents.strategist.service import SONNET_MODEL
from argos.config import get_settings

logger = logging.getLogger("argos.agents.score.claude")

CLAUDE_MAX_TOKENS = 600
DELTA_MIN = -0.15
DELTA_MAX = 0.15
PROMPT_VERSION = "score_claude_v1.0"


SYSTEM_PROMPT = """Eres el analista crediticio senior del Score Engine de RODDOS.

Tu rol: revisar coherencia entre KYC declarado, datos de partners (RiskSeal, AUCO,
Palenca) y textos de documentos. Tu output ajusta el score del modelo XGBoost en
±0.15 puntos · narrativa auditable.

CRITERIOS:

1. Coherencia KYC vs partners:
   - Si tipo_empleo dice "delivery" pero Palenca no devuelve plataforma → señal débil.
   - Si nombre KYC y nombre AUCO no calzan → fraude potencial.
   - Si ingreso declarado >> ingreso Palenca verificado → fraude potencial.

2. Señales en documentos (recibos, extractos):
   - Texto incoherente, fecha futura, firma inexistente → fraude.
   - Patrón de gastos coherente con ingreso → señal positiva.

3. Producto pedido vs perfil:
   - credito_rdx_leasing (moto nueva) requiere mayor estabilidad que credito_rodante (repuestos).
   - Mototaxista 2+ años + score_comportamental A+ → bonus.

OUTPUT JSON ESTRICTO:
{
  "delta": float entre -0.15 y +0.15,
  "narrativa": "string ≤300 chars · audit-trail, sin markdown",
  "fraude_detectado": bool
}

Sin texto antes ni después del JSON."""


@dataclass
class ClaudeScoreResult:
    delta: float           # [-0.15, +0.15]
    narrativa: str         # auditable (ROG-S4)
    fraude_detectado: bool
    prompt_version: str = PROMPT_VERSION
    tokens_input: int = 0
    tokens_output: int = 0


class ClaudeScorer:
    """Stateless · Sonnet 4.6 con cache_control efímero del system prompt."""

    def __init__(
        self,
        api_key: str = "",
        model: str = SONNET_MODEL,
        client: Any | None = None,
    ) -> None:
        self._api_key = api_key or get_settings().anthropic_api_key
        self._model = model
        self._client = client  # inyectable para tests

    @property
    def enabled(self) -> bool:
        return bool(self._api_key) or self._client is not None

    async def analyze(
        self,
        kyc_data: dict[str, Any],
        document_texts: list[str] | None = None,
        partner_data: dict[str, Any] | None = None,
    ) -> ClaudeScoreResult:
        if not self.enabled:
            logger.warning("claude_scorer_skipped_no_key")
            return ClaudeScoreResult(
                delta=0.0,
                narrativa="Sin ANTHROPIC_API_KEY · ajuste cualitativo omitido.",
                fraude_detectado=False,
            )

        client = self._client
        if client is None:
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic(api_key=self._api_key)

        user_msg = (
            f"KYC declarado:\n```json\n{json.dumps(kyc_data, ensure_ascii=False, default=str)}\n```\n\n"
            f"Datos de partners:\n```json\n{json.dumps(partner_data or {}, ensure_ascii=False, default=str)}\n```\n\n"
            f"Textos de documentos (si hay):\n"
            + ("\n---\n".join((document_texts or [])[:4]) or "(sin documentos)")
            + "\n\nDevuelve el JSON con delta, narrativa, fraude_detectado."
        )

        try:
            resp = await client.messages.create(
                model=self._model,
                max_tokens=CLAUDE_MAX_TOKENS,
                system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user_msg}],
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("claude_scorer_failed")
            return ClaudeScoreResult(
                delta=0.0,
                narrativa=f"Análisis Claude falló ({type(exc).__name__}) · revisión manual sugerida.",
                fraude_detectado=False,
            )

        text = ""
        with contextlib.suppress(AttributeError, IndexError, TypeError):
            text = resp.content[0].text or ""

        delta, narrativa, fraude = _parse_claude_response(text)

        usage = getattr(resp, "usage", None)
        return ClaudeScoreResult(
            delta=max(DELTA_MIN, min(DELTA_MAX, float(delta))),
            narrativa=narrativa[:300],
            fraude_detectado=bool(fraude),
            tokens_input=int(getattr(usage, "input_tokens", 0) or 0),
            tokens_output=int(getattr(usage, "output_tokens", 0) or 0),
        )


def _parse_claude_response(text: str) -> tuple[float, str, bool]:
    """Parsing defensivo · acepta JSON con fences markdown · fallback a (0, msg, False)."""
    if not text:
        return 0.0, "Claude no devolvió contenido · revisión manual.", False
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # remover fence
        lines = cleaned.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return 0.0, f"Parsing JSON falló · texto: {text[:200]}", False
    if not isinstance(data, dict):
        return 0.0, "Respuesta de Claude no es objeto JSON.", False
    return (
        float(data.get("delta") or 0),
        str(data.get("narrativa") or ""),
        bool(data.get("fraude_detectado", False)),
    )
