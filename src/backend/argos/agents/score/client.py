"""ScoreEngineClient · cliente HTTP del Score Engine externo (repo de Iván).

ARGOS hace pass-through: WhatsApp Agent (o el frontend de pruebas) envía la
solicitud, ARGOS la reenvía a `SCORE_ENGINE_API_URL/v1/evaluate`, el repo de
Iván la evalúa y persiste en MongoDB compartido. ARGOS no aplica reglas duras
ni llama Claude directamente.

Skip silencioso si `SCORE_ENGINE_API_URL` no configurado → devuelve mock con
`decision="no_configurado"` · permite que el frontend renderice un estado claro
en dev/staging sin Score Engine disponible.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from argos.config import get_settings

logger = logging.getLogger("argos.agents.score.client")

DEFAULT_TIMEOUT_SECONDS = 10.0
MAX_RETRIES = 1


class ScoreEngineError(Exception):
    def __init__(self, status: int, message: str) -> None:
        self.status = status
        self.message = message
        super().__init__(f"ScoreEngine {status}: {message}")


@dataclass
class ScoreEngineResponse:
    decision: str
    score_final: int
    solicitud_id: str
    raw: dict[str, Any]


class ScoreEngineClient:
    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if not base_url:
            settings = get_settings()
            self._base_url = settings.score_engine_api_url.rstrip("/")
            self._api_key = api_key or settings.score_engine_api_key
        else:
            self._base_url = base_url.rstrip("/")
            self._api_key = api_key
        self._timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self._base_url)

    async def evaluate(
        self,
        payload: dict[str, Any],
        *,
        client: httpx.AsyncClient | None = None,
    ) -> ScoreEngineResponse:
        if not self.enabled:
            logger.warning("score_engine_skipped_no_url")
            return ScoreEngineResponse(
                decision="no_configurado",
                score_final=0,
                solicitud_id="",
                raw={"detail": "SCORE_ENGINE_API_URL no configurado"},
            )

        headers: dict[str, str] = {"Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        last_exc: Exception | None = None
        owns_client = client is None
        if owns_client:
            client = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout, headers=headers)
        try:
            for attempt in range(MAX_RETRIES + 1):
                try:
                    resp = await client.post("/v1/evaluate", json=payload, headers=headers)
                except httpx.HTTPError as exc:
                    last_exc = exc
                    logger.warning(
                        "score_engine_http_error",
                        extra={"attempt": attempt, "error": str(exc)[:200]},
                    )
                    if attempt < MAX_RETRIES:
                        continue
                    raise ScoreEngineError(0, f"http_error: {type(exc).__name__}") from exc
                if resp.status_code >= 500 and attempt < MAX_RETRIES:
                    continue
                if resp.status_code >= 400:
                    raise ScoreEngineError(resp.status_code, resp.text[:300])
                try:
                    data = resp.json()
                except ValueError:
                    raise ScoreEngineError(resp.status_code, "respuesta no-JSON")  # noqa: B904
                if not isinstance(data, dict):
                    raise ScoreEngineError(resp.status_code, "respuesta no es objeto JSON")
                return ScoreEngineResponse(
                    decision=str(data.get("decision", "")),
                    score_final=int(data.get("score_final") or 0),
                    solicitud_id=str(data.get("solicitud_id", "")),
                    raw=data,
                )
            # Inalcanzable, pero para satisfacer mypy
            raise ScoreEngineError(0, f"unreachable · last={last_exc}")
        finally:
            if owns_client and client is not None:
                await client.aclose()
