"""Cliente async para Twilio WhatsApp · Build market-intelligence-complete.

API: `POST https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json`
Auth: HTTP Basic con (account_sid, auth_token).
Body: form-urlencoded con `From`, `To`, `Body`.

`From` y `To` esperan formato `whatsapp:+57XXXXXXXXXX` (sandbox o número productivo).

Skip silencioso si `TWILIO_ACCOUNT_SID` o `TWILIO_AUTH_TOKEN` están vacíos.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("argos.partners.twilio")

TWILIO_BASE_URL = "https://api.twilio.com/2010-04-01"
DEFAULT_TIMEOUT_SECONDS = 15.0
MAX_BODY_LENGTH = 1600  # Twilio limit


class TwilioError(Exception):
    def __init__(self, status: int, message: str) -> None:
        self.status = status
        self.message = message
        super().__init__(f"Twilio {status}: {message}")


class TwilioWhatsAppClient:
    """Async cliente · context manager · skip silencioso sin credenciales."""

    def __init__(
        self,
        account_sid: str = "",
        auth_token: str = "",
        whatsapp_from: str = "",
        whatsapp_to: str = "",
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._account_sid = account_sid
        self._auth_token = auth_token
        self._from = whatsapp_from
        self._default_to = whatsapp_to
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def enabled(self) -> bool:
        return bool(self._account_sid and self._auth_token and self._from)

    @property
    def default_to(self) -> str:
        return self._default_to

    async def __aenter__(self) -> TwilioWhatsAppClient:
        if self.enabled and self._client is None:
            self._client = httpx.AsyncClient(
                base_url=TWILIO_BASE_URL,
                timeout=self._timeout,
                auth=(self._account_sid, self._auth_token),
            )
            self._owns_client = True
        else:
            self._owns_client = False
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if self._client is not None and getattr(self, "_owns_client", False):
            await self._client.aclose()
            self._client = None

    async def send_whatsapp(
        self,
        body: str,
        *,
        to: str = "",
    ) -> dict[str, Any]:
        """Envía un WhatsApp · devuelve dict de Twilio o `{}` si no enabled."""
        if not self.enabled or self._client is None:
            logger.warning("twilio_skipped_no_credentials")
            return {}

        target = to or self._default_to
        if not target:
            raise TwilioError(0, "Sin destino · pasa `to=` o setea TWILIO_WHATSAPP_TO")

        payload = {
            "From": self._from,
            "To": target,
            "Body": body[:MAX_BODY_LENGTH],
        }
        path = f"/Accounts/{self._account_sid}/Messages.json"
        try:
            resp = await self._client.post(path, data=payload)
        except httpx.HTTPError as exc:
            logger.warning("twilio_http_error", extra={"error": str(exc)[:200]})
            raise TwilioError(0, f"http_error: {type(exc).__name__}") from exc

        if resp.status_code >= 400:
            raise TwilioError(resp.status_code, resp.text[:300])

        try:
            return resp.json()
        except ValueError:
            return {}
