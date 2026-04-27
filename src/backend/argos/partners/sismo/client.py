"""Cliente async para SISMO V2 (ERP de RODDOS) · Build 4.1 (read-only).

ARGOS consume SISMO V2 como fuente de verdad de inventario, ventas y loanbook.
Comunicación vía HTTPS con header `Authorization: Bearer {api_key}`. ROG-A11
exige aislamiento de credenciales · esta key da SOLO read sobre los endpoints
listados aquí · cualquier escritura debe ir por el admin web (otro key).

Endpoints Build 4.1 (read-only):
- `GET /api/inventory/repuestos` → SKUs activos {sku, nombre, stock, costo, precio, dias_inventario}
- `GET /api/inventory/slow_movers` → SKUs con >45 días sin rotación
- `GET /api/sales/daily?date=YYYY-MM-DD` → ventas del día por SKU

Skip silencioso si `SISMO_API_URL` o `SISMO_API_KEY` están vacíos · `enabled=False` y todas
las operaciones devuelven listas vacías. Útil para CI y entornos dev sin acceso a SISMO.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("argos.partners.sismo")

DEFAULT_TIMEOUT_SECONDS = 30.0


class SismoError(Exception):
    def __init__(self, status: int, message: str) -> None:
        self.status = status
        self.message = message
        super().__init__(f"SISMO {status}: {message}")


class SismoClient:
    """Async context manager · skip silencioso sin URL+key."""

    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def enabled(self) -> bool:
        return bool(self._base_url and self._api_key)

    async def __aenter__(self) -> SismoClient:
        # `_client` puede venir pre-inyectado (tests con httpx.MockTransport).
        if self.enabled and self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Accept": "application/json",
                },
            )
            self._owns_client = True
        else:
            self._owns_client = False
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if self._client is not None and getattr(self, "_owns_client", False):
            await self._client.aclose()
            self._client = None

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if not self.enabled or self._client is None:
            logger.warning("sismo_skipped_no_credentials", extra={"path": path})
            return None
        try:
            resp = await self._client.get(path, params=params or {})
        except httpx.HTTPError as exc:
            logger.warning("sismo_http_error", extra={"path": path, "error": str(exc)[:200]})
            raise SismoError(0, f"http_error: {type(exc).__name__}") from exc

        if resp.status_code == 401:
            raise SismoError(401, "SISMO key inválida o expirada")
        if resp.status_code == 403:
            raise SismoError(403, "SISMO scope insuficiente · revisa permisos read")
        if resp.status_code == 429:
            raise SismoError(429, "SISMO rate limited")
        if resp.status_code >= 400:
            raise SismoError(resp.status_code, resp.text[:200])

        try:
            return resp.json()
        except ValueError:
            return None

    async def get_inventory(self) -> list[dict[str, Any]]:
        """Lista de repuestos activos con stock, precio, costo, días en inventario.

        Devuelve `[]` si no enabled o si la respuesta no es lista.
        El parsing defensivo acepta `{items: [...]}` o lista directa.
        """
        data = await self._get("/api/inventory/repuestos")
        return _coerce_list(data)

    async def get_slow_movers(self) -> list[dict[str, Any]]:
        """SKUs con >45 días sin rotación · `[]` si no enabled."""
        data = await self._get("/api/inventory/slow_movers")
        return _coerce_list(data)

    async def get_daily_sales(self, fecha: str) -> list[dict[str, Any]]:
        """Ventas del día (`YYYY-MM-DD`) por SKU · `[]` si no enabled."""
        data = await self._get("/api/sales/daily", params={"date": fecha})
        return _coerce_list(data)


def _coerce_list(data: Any) -> list[dict[str, Any]]:
    """SISMO V2 puede devolver `[...]` directo o `{items: [...]}` o `{data: [...]}`."""
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    if isinstance(data, dict):
        for key in ("items", "data", "results"):
            inner = data.get(key)
            if isinstance(inner, list):
                return [d for d in inner if isinstance(d, dict)]
    return []
