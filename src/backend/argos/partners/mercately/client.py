"""MercatelyClient async · WhatsApp BSP para ARGOS (Build 3.1 · Capa 1).

URL base: https://app.mercately.com/retailers/api/v1
Auth: header ``api-key`` (lowercase, NO Bearer).
Phone format: 12 dígitos ``57XXXXXXXXXX`` sin ``+``.

Skip silencioso si ``MERCATELY_API_KEY`` está vacía.
"""
from __future__ import annotations

import logging
import re
from typing import Any

import httpx

logger = logging.getLogger("argos.partners.mercately")

MERCATELY_BASE_URL = "https://app.mercately.com/retailers/api/v1"
DEFAULT_TIMEOUT_SECONDS = 20.0


class MercatelyError(Exception):
    def __init__(self, status: int, message: str) -> None:
        self.status = status
        self.message = message
        super().__init__(f"Mercately {status}: {message}")


_PHONE_RE = re.compile(r"^\d{10,12}$")


def normalize_phone(raw: str) -> str:
    """Normaliza teléfono colombiano a formato Mercately 12 dígitos (57XXXXXXXXXX).

    Acepta: +573001234567, 573001234567, 3001234567, 03001234567.
    Retorna: 573001234567.
    """
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 10:
        digits = f"57{digits}"
    if len(digits) != 12 or not digits.startswith("57"):
        raise ValueError(f"Phone inválido para Colombia: {raw!r} → {digits}")
    return digits


class MercatelyClient:
    """Async client · context manager · skip silencioso sin API key."""

    def __init__(
        self,
        api_key: str = "",
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def enabled(self) -> bool:
        return bool(self._api_key)

    async def __aenter__(self) -> MercatelyClient:
        if self.enabled and self._client is None:
            self._client = httpx.AsyncClient(
                base_url=MERCATELY_BASE_URL,
                timeout=self._timeout,
                headers={"api-key": self._api_key},
            )
            self._owns_client = True
        else:
            self._owns_client = False
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if self._client is not None and getattr(self, "_owns_client", False):
            await self._client.aclose()
            self._client = None

    def _check_enabled(self) -> bool:
        if not self.enabled or self._client is None:
            logger.warning("mercately_skipped_no_api_key")
            return False
        return True

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self._check_enabled():
            return {}
        assert self._client is not None
        try:
            resp = await self._client.request(method, path, json=json, params=params)
        except httpx.HTTPError as exc:
            logger.warning("mercately_http_error", extra={"error": str(exc)[:200]})
            raise MercatelyError(0, f"http_error: {type(exc).__name__}") from exc

        if resp.status_code >= 400:
            raise MercatelyError(resp.status_code, resp.text[:300])

        try:
            return resp.json()
        except ValueError:
            return {}

    async def send_template(
        self,
        phone: str,
        template_id: str,
        params: list[str] | None = None,
    ) -> dict[str, Any]:
        """Envía template aprobado vía Mercately."""
        phone = normalize_phone(phone)
        body: dict[str, Any] = {
            "phone": phone,
            "template_id": template_id,
        }
        if params:
            body["params"] = params
        result = await self._request("POST", "/whatsapp/send_notification_by_id", json=body)
        logger.info("mercately_template_sent", extra={"phone": phone[-4:], "template": template_id})
        return result

    async def send_text(self, phone: str, message: str) -> dict[str, Any]:
        """Envía texto libre (ventana 24h)."""
        phone = normalize_phone(phone)
        result = await self._request(
            "POST",
            "/whatsapp/send_message",
            json={"phone": phone, "message": message[:4096]},
        )
        logger.info("mercately_text_sent", extra={"phone": phone[-4:]})
        return result

    async def get_customer_by_phone(self, phone: str) -> dict[str, Any]:
        """Obtiene perfil de cliente por teléfono."""
        phone = normalize_phone(phone)
        return await self._request("GET", f"/customers/{phone}")

    async def get_customer_messages(
        self,
        phone: str,
        page: int = 1,
    ) -> dict[str, Any]:
        """Obtiene conversaciones de un phone (endpoint per-phone, NO global).

        El global ``/whatsapp_conversations`` da HTTP 500 (bug confirmado Mercately).
        """
        phone = normalize_phone(phone)
        return await self._request(
            "GET",
            f"/customers/{phone}/whatsapp_conversations",
            params={"page": page},
        )

    async def create_customer(
        self,
        phone: str,
        first_name: str = "",
        last_name: str = "",
        **extra: Any,
    ) -> dict[str, Any]:
        """Crea cliente en Mercately."""
        phone = normalize_phone(phone)
        body: dict[str, Any] = {"phone": phone}
        if first_name:
            body["first_name"] = first_name[:100]
        if last_name:
            body["last_name"] = last_name[:100]
        body.update(extra)
        result = await self._request("POST", "/customers", json=body)
        logger.info("mercately_customer_created", extra={"phone": phone[-4:]})
        return result
