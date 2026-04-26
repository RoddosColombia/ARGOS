"""Cliente async para SerpAPI · Build 1.3 (Google Trends).

Endpoint usado: GET https://serpapi.com/search.json?engine=google_trends&q=...&geo=CO&date=now+7-d&api_key=...

Output relevante (`interest_over_time.timeline_data`): lista de puntos con
`date` (string) y `values[].extracted_value` (entero 0-100).
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("argos.partners.serpapi")

SERPAPI_BASE_URL = "https://serpapi.com"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_GEO = "CO"


class SerpApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        self.status = status
        self.message = message
        super().__init__(f"SerpAPI {status}: {message}")


class SerpApiClient:
    """Cliente SerpAPI · context manager async · skip silencioso sin api_key."""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = SERPAPI_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def enabled(self) -> bool:
        return bool(self._api_key)

    async def __aenter__(self) -> SerpApiClient:
        if self.enabled:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout)
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def google_trends(
        self,
        keyword: str,
        *,
        geo: str = DEFAULT_GEO,
        date_range: str = "now 7-d",
    ) -> dict[str, Any]:
        """Devuelve el JSON crudo del response de SerpAPI · `{}` si no enabled."""
        return await self._search_json(
            keyword,
            params={
                "engine": "google_trends",
                "q": keyword,
                "geo": geo,
                "date": date_range,
            },
        )

    async def google_ads_transparency(
        self,
        keyword: str,
        *,
        region: str = DEFAULT_GEO,
    ) -> dict[str, Any]:
        """Búsqueda en Google Ads Transparency Center · `{}` si no enabled."""
        return await self._search_json(
            keyword,
            params={
                "engine": "google_ads_transparency_center",
                "text": keyword,
                "region": region,
            },
        )

    async def _search_json(self, label: str, *, params: dict[str, Any]) -> dict[str, Any]:
        """Helper compartido · GET /search.json con manejo de errores común."""
        if not self.enabled or self._client is None:
            logger.warning("serpapi_skipped_no_key", extra={"label": label})
            return {}

        full_params = {**params, "api_key": self._api_key}
        try:
            resp = await self._client.get("/search.json", params=full_params)
        except httpx.HTTPError as exc:
            logger.warning("serpapi_http_error", extra={"label": label, "error": str(exc)[:200]})
            raise SerpApiError(0, f"http_error: {type(exc).__name__}") from exc

        if resp.status_code == 401:
            raise SerpApiError(401, "SerpAPI key inválida")
        if resp.status_code == 429:
            raise SerpApiError(429, "SerpAPI rate limited")
        if resp.status_code >= 400:
            raise SerpApiError(resp.status_code, resp.text[:200])

        data = resp.json()
        if not isinstance(data, dict):
            return {}
        return data
