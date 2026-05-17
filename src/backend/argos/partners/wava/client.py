"""WavaClient async · pasarela Nequi/Daviplata para ARGOS (Build 3.3 · Capa 1).

URL dev: https://api.dev.wava.co/v1
URL prod: https://api.wava.co/v1
Auth: header ``merchant-key`` con WAVA_MERCHANT_KEY.

Skip silencioso si ``WAVA_MERCHANT_KEY`` está vacía.

Refs: phase_3/build_3.3 · ROG-A1 (approval humano para dinero)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger("argos.partners.wava")

DEFAULT_TIMEOUT_SECONDS = 30.0


class WavaError(Exception):
    def __init__(self, status: int, message: str) -> None:
        self.status = status
        self.message = message
        super().__init__(f"Wava {status}: {message}")


@dataclass(frozen=True, slots=True)
class WavaShopper:
    first_name: str
    last_name: str
    email: str
    phone_number: str
    country: str = "CO"
    id_number: str = ""
    id_type: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "phone_number": self.phone_number,
            "country": self.country,
            "id_number": self.id_number,
            "id_type": self.id_type,
        }


@dataclass(frozen=True, slots=True)
class WavaOrder:
    order_id: str = ""
    status: str = ""
    amount: float = 0.0
    currency: str = "COP"
    description: str = ""
    payment_url: str = ""
    order_key: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> WavaOrder:
        return cls(
            order_id=str(data.get("id", data.get("order_id", ""))),
            status=data.get("status", ""),
            amount=float(data.get("amount", 0)),
            currency=data.get("currency", "COP"),
            description=data.get("description", ""),
            payment_url=data.get("payment_url", data.get("url", "")),
            order_key=data.get("order_key", ""),
            raw=data,
        )


class WavaClient:
    """Async client · context manager · skip silencioso sin merchant key."""

    def __init__(
        self,
        merchant_key: str = "",
        base_url: str = "https://api.dev.wava.co/v1",
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._merchant_key = merchant_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._owns_client = False

    @property
    def enabled(self) -> bool:
        return bool(self._merchant_key)

    async def __aenter__(self) -> WavaClient:
        if self.enabled and self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                headers={"merchant-key": self._merchant_key},
            )
            self._owns_client = True
        else:
            self._owns_client = False
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    def _check_enabled(self) -> bool:
        if not self.enabled or self._client is None:
            logger.warning("wava_skipped_no_merchant_key")
            return False
        return True

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self._check_enabled():
            return {}
        assert self._client is not None
        try:
            resp = await self._client.request(method, path, json=json)
        except httpx.HTTPError as exc:
            logger.warning("wava_http_error", extra={"error": str(exc)[:200]})
            raise WavaError(0, f"http_error: {type(exc).__name__}") from exc

        if resp.status_code >= 400:
            raise WavaError(resp.status_code, resp.text[:300])

        try:
            return resp.json()
        except ValueError:
            return {}

    async def create_order(
        self,
        amount: int,
        description: str,
        shopper: WavaShopper,
        gateway_id: int = 1,
        order_key: str = "",
    ) -> WavaOrder:
        """POST /v1/orders — crea orden de pago."""
        body: dict[str, Any] = {
            "amount": amount,
            "description": description[:200],
            "currency": "COP",
            "shopper": shopper.to_dict(),
            "payment_gateway": {"id_payment_gateway": gateway_id},
        }
        if order_key:
            body["order_key"] = order_key

        data = await self._request("POST", "/orders", json=body)
        order = WavaOrder.from_response(data)
        logger.info(
            "wava_order_created",
            extra={"order_id": order.order_id, "amount": amount},
        )
        return order

    async def get_order(self, order_id: str) -> WavaOrder:
        """GET /v1/orders/{orderId} — consulta estado de orden."""
        data = await self._request("GET", f"/orders/{order_id}")
        return WavaOrder.from_response(data)

    async def get_gateways(self) -> list[dict[str, Any]]:
        """GET /v1/orders/paymentGateways — lista gateways disponibles."""
        data = await self._request("GET", "/orders/paymentGateways")
        if isinstance(data, dict):
            return data.get("data", data.get("gateways", []))
        return []

    async def submit_daviplata_otp(
        self,
        order_id: str,
        otp: str,
    ) -> dict[str, Any]:
        """POST /v1/orders/{id}/daviplata-otp — envía OTP Daviplata."""
        return await self._request(
            "POST",
            f"/orders/{order_id}/daviplata-otp",
            json={"otp": otp},
        )
