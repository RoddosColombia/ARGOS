"""Cliente async para Apify · Build 1.1.

Build 1.1 usa el actor `apify/facebook-marketplace-scraper` para obtener
listings de FB Marketplace (sin OAuth · scraping con respeto a rate limits).

Docs: https://docs.apify.com/api/v2#tag/Acts
Endpoint usado: `POST /v2/acts/{actorId}/run-sync-get-dataset-items?token=...`

Output schema típico del actor (puede variar entre versiones del actor):
- title · price (string con símbolo) · currency · location · url · image
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("argos.partners.apify")

APIFY_BASE_URL = "https://api.apify.com"
DEFAULT_TIMEOUT_SECONDS = 60.0  # Apify run-sync puede tardar
DEFAULT_FB_ACTOR_ID = "apify~facebook-marketplace-scraper"
DEFAULT_COUNTRY = "co"


class ApifyError(Exception):
    def __init__(self, status: int, message: str) -> None:
        self.status = status
        self.message = message
        super().__init__(f"Apify {status}: {message}")


class ApifyClient:
    """Cliente Apify · usar como context manager.

    Skip silencioso si `api_token` está vacío · `enabled` retorna False y los
    métodos de scraping devuelven listas vacías. Esto permite que Scout llame
    a Apify sin verificar token explícitamente · Build 1.1 puede correr sin
    Apify configurado y solo pega contra MELI.
    """

    def __init__(
        self,
        api_token: str = "",
        base_url: str = APIFY_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._api_token = api_token
        self._base_url = base_url
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def enabled(self) -> bool:
        return bool(self._api_token)

    async def __aenter__(self) -> ApifyClient:
        if self.enabled:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout)
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def fb_marketplace_search(
        self,
        query: str,
        *,
        country: str = DEFAULT_COUNTRY,
        max_items: int = 20,
        actor_id: str = DEFAULT_FB_ACTOR_ID,
    ) -> list[dict[str, Any]]:
        """Corre el actor FB Marketplace y devuelve los items raw del dataset.

        Si el cliente no está habilitado (sin token), devuelve lista vacía
        y loggea un warning sin levantar excepción.
        """
        if not self.enabled or self._client is None:
            logger.warning("apify_skipped_no_token", extra={"query": query})
            return []

        actor_input = {
            "search": query,
            "country": country,
            "maxItems": max_items,
        }
        try:
            resp = await self._client.post(
                f"/v2/acts/{actor_id}/run-sync-get-dataset-items",
                params={"token": self._api_token},
                json=actor_input,
            )
        except httpx.HTTPError as exc:
            logger.warning("apify_http_error", extra={"query": query, "error": str(exc)[:200]})
            raise ApifyError(0, f"http_error: {type(exc).__name__}") from exc

        if resp.status_code == 401:
            raise ApifyError(401, "Apify token inválido")
        if resp.status_code == 429:
            raise ApifyError(429, "Apify rate limited")
        if resp.status_code >= 400:
            raise ApifyError(resp.status_code, resp.text[:200])

        data = resp.json()
        if not isinstance(data, list):
            logger.warning("apify_unexpected_response_shape", extra={"shape": type(data).__name__})
            return []
        return data
