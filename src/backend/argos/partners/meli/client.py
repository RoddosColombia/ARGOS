"""Cliente async para la API pública de Mercado Libre (MELI).

Build 1.0: solo endpoints públicos (`/sites/MCO/search`, `/items/{id}`). No
requiere OAuth · se agrega cuando se necesiten datos privados de sellers.

Docs: https://developers.mercadolibre.com.co/
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger("argos.partners.meli")

MELI_BASE_URL = "https://api.mercadolibre.com"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_SITE = "MCO"  # Colombia


class MeliError(Exception):
    """Raised cuando la API MELI devuelve un error no recuperable."""

    def __init__(self, status: int, message: str) -> None:
        self.status = status
        self.message = message
        super().__init__(f"MELI {status}: {message}")


class MeliClient:
    """Cliente async · usar como context manager.

    Ejemplo:
        async with MeliClient() as meli:
            items = await meli.search(query="aceite moto", limit=20)
    """

    def __init__(
        self,
        base_url: str = MELI_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_concurrency: int = 5,
    ) -> None:
        self._base_url = base_url
        self._timeout = timeout
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> MeliClient:
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout)
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _require_client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("MeliClient debe usarse como async context manager")
        return self._client

    async def search(
        self,
        query: str,
        *,
        site_id: str = DEFAULT_SITE,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """GET /sites/{site_id}/search?q=...&limit=...&offset=... → lista de items.

        Retorna `results` del response. En caso de 429 lanza `MeliError(429)`.
        """
        client = self._require_client()
        async with self._semaphore:
            resp = await client.get(
                f"/sites/{site_id}/search",
                params={"q": query, "limit": limit, "offset": offset},
            )
        if resp.status_code == 429:
            logger.warning("meli_rate_limited", extra={"query": query, "status": 429})
            raise MeliError(429, "Rate limited")
        resp.raise_for_status()
        data = resp.json()
        return list(data.get("results", []))

    async def item(self, item_id: str) -> dict[str, Any]:
        """GET /items/{item_id} → detalle completo. 404 → MeliError(404)."""
        client = self._require_client()
        async with self._semaphore:
            resp = await client.get(f"/items/{item_id}")
        if resp.status_code == 404:
            raise MeliError(404, f"Item {item_id} no encontrado")
        if resp.status_code == 429:
            raise MeliError(429, "Rate limited")
        resp.raise_for_status()
        return dict(resp.json())
