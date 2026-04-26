"""Trends Agent · interés Google Trends por keyword · Build 1.3.

Persiste resultados en `keywords` y emite `trends.keyword.spike` cuando el
delta 7d > 30% (umbral hardcoded por ahora · DT futura para hacerlo
configurable por workspace).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.config import get_settings
from argos.db import collections as col
from argos.db.events import publish_trends_keyword_spike
from argos.partners.serpapi.client import SerpApiClient, SerpApiError

logger = logging.getLogger("argos.agents.trends")

SPIKE_THRESHOLD_PCT = 30.0


@dataclass
class TrendResult:
    keyword: str
    interest_over_time: int  # 0-100 · último punto del timeline
    delta_7d_pct: float
    pico_detectado: bool


def _parse_serpapi_response(keyword: str, raw: dict[str, Any]) -> TrendResult:
    """Extrae interest + delta del JSON de SerpAPI · tolera ausencia de campos.

    Si no hay `interest_over_time.timeline_data`, devuelve un TrendResult con
    ceros (no levanta · evita romper el job por una keyword sin volumen).
    """
    timeline = (
        raw.get("interest_over_time", {}).get("timeline_data", [])
        if isinstance(raw, dict)
        else []
    )
    values: list[int] = []
    for point in timeline:
        if not isinstance(point, dict):
            continue
        vs = point.get("values") or []
        if vs and isinstance(vs[0], dict):
            ev = vs[0].get("extracted_value")
            if isinstance(ev, (int, float)):
                values.append(int(ev))

    if not values:
        return TrendResult(keyword=keyword, interest_over_time=0, delta_7d_pct=0.0, pico_detectado=False)

    last = values[-1]
    first = values[0]
    delta_pct = ((last - first) / first * 100.0) if first > 0 else 0.0
    pico = delta_pct > SPIKE_THRESHOLD_PCT or last >= 80
    return TrendResult(
        keyword=keyword,
        interest_over_time=last,
        delta_7d_pct=round(delta_pct, 2),
        pico_detectado=pico,
    )


class TrendsAgent:
    """Agente Trends · usa SerpApiClient inyectable o construido desde settings."""

    def __init__(self, client: SerpApiClient | None = None) -> None:
        if client is not None:
            self._client = client
            self._owned = False
        else:
            settings = get_settings()
            self._client = SerpApiClient(api_key=settings.serpapi_api_key)
            self._owned = True

    async def __aenter__(self) -> TrendsAgent:
        if self._owned:
            await self._client.__aenter__()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if self._owned:
            await self._client.__aexit__(None, None, None)

    async def fetch_keyword_trends(self, keywords: list[str]) -> list[TrendResult]:
        """Itera keywords secuencialmente · errores aislados por keyword."""
        if not self._client.enabled:
            logger.warning("trends_agent_disabled_no_serpapi_key")
            return []

        results: list[TrendResult] = []
        for kw in keywords:
            try:
                raw = await self._client.google_trends(kw)
                results.append(_parse_serpapi_response(kw, raw))
            except SerpApiError as exc:
                logger.warning("trends_serpapi_error", extra={"keyword": kw, "status": exc.status})
            except Exception:  # noqa: BLE001 — aislar falla por keyword
                logger.exception("trends_keyword_failed", extra={"keyword": kw})
        return results


async def refresh_trends(
    db: AsyncIOMotorDatabase,
    *,
    workspace_id: str = "RODDOS",
    agent: TrendsAgent | None = None,
) -> dict[str, int]:
    """Job: lee watch_queries con source='all', fetcha trends, upsert en keywords.

    Emite `trends.keyword.spike` por cada keyword con delta > 30%.
    """
    cursor = db[col.WATCH_QUERIES].find(
        {"workspace_id": workspace_id, "activa": True, "source": "all"}
    )
    queries = await cursor.to_list(length=None)
    keywords = [q["query"] for q in queries]
    if not keywords:
        return {"keywords_processed": 0, "spikes_detected": 0}

    own_agent = agent is None
    if own_agent:
        agent = TrendsAgent()
        await agent.__aenter__()

    spikes = 0
    try:
        results = await agent.fetch_keyword_trends(keywords)
        now = datetime.now(tz=UTC)

        for r in results:
            await db[col.KEYWORDS].update_one(
                {"workspace_id": workspace_id, "keyword": r.keyword},
                {
                    "$set": {
                        "interest_over_time": r.interest_over_time,
                        "growth_pct_7d": r.delta_7d_pct,
                        "spike_detected": r.pico_detectado,
                        "vertical": "repuestos-motos",
                        "updated_at": now,
                    },
                    "$setOnInsert": {
                        "workspace_id": workspace_id,
                        "keyword": r.keyword,
                        "created_at": now,
                    },
                },
                upsert=True,
            )
            if r.pico_detectado:
                spikes += 1
                await publish_trends_keyword_spike(
                    db,
                    workspace_id=workspace_id,
                    keyword=r.keyword,
                    interest_over_time=r.interest_over_time,
                    delta_7d_pct=r.delta_7d_pct,
                )
    finally:
        if own_agent:
            await agent.__aexit__(None, None, None)

    logger.info(
        "trends_refresh_done",
        extra={"keywords_processed": len(keywords), "spikes_detected": spikes},
    )
    return {"keywords_processed": len(keywords), "spikes_detected": spikes}
