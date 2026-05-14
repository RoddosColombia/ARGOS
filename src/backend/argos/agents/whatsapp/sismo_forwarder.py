"""SISMO forwarder · reenvía mensajes inbound clasificados como SISMO (Build 3.1).

POST a SISMO_INBOUND_WEBHOOK_URL con header X-Mercately-Secret.
Non-blocking en caso de fallo de SISMO (log + continúa).
Emite evento whatsapp.message.forwarded_sismo al bus.

Refs: phase_3/build_3.1 · ROG-A11 (comunicación vía APIs autenticadas)
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger("argos.agents.whatsapp.sismo_forwarder")

DEFAULT_TIMEOUT_SECONDS = 10.0


class SismoForwardError(Exception):
    def __init__(self, status: int, message: str) -> None:
        self.status = status
        self.message = message
        super().__init__(f"SismoForward {status}: {message}")


async def forward_to_sismo(
    *,
    phone: str,
    message_text: str,
    intent: str,
    confidence: float,
    mercately_conversation_id: str = "",
    sismo_webhook_url: str,
    webhook_secret: str = "",
    db: AsyncIOMotorDatabase | None = None,
    workspace_id: str = "RODDOS",
) -> dict[str, Any]:
    """Reenvía mensaje inbound a SISMO vía webhook.

    Non-blocking: si SISMO falla, loggea y retorna {forwarded: False}.
    """
    if not sismo_webhook_url:
        logger.warning("sismo_forward_skipped_no_url")
        return {"forwarded": False, "reason": "no_sismo_webhook_url"}

    payload = {
        "phone": phone,
        "message": message_text[:4096],
        "intent": intent,
        "confidence": round(confidence, 3),
        "source": "argos_inbound_poller",
    }
    if mercately_conversation_id:
        payload["mercately_conversation_id"] = mercately_conversation_id

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if webhook_secret:
        headers["X-Mercately-Secret"] = webhook_secret

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
            resp = await client.post(sismo_webhook_url, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        logger.warning(
            "sismo_forward_http_error",
            extra={"error": str(exc)[:200], "phone": phone[-4:]},
        )
        return {"forwarded": False, "reason": f"http_error: {type(exc).__name__}"}

    forwarded = resp.status_code < 400
    if not forwarded:
        logger.warning(
            "sismo_forward_failed",
            extra={"status": resp.status_code, "phone": phone[-4:]},
        )

    if db is not None:
        from argos.db.events import publish_event
        try:
            await publish_event(
                db,
                event_type="whatsapp.message.forwarded_sismo",
                workspace_id=workspace_id,
                producer="sismo_forwarder",
                payload={
                    "phone_last4": phone[-4:] if phone else "",
                    "intent": intent,
                    "forwarded": forwarded,
                    "sismo_status": resp.status_code,
                },
            )
        except Exception:  # noqa: BLE001
            logger.exception("sismo_forward_event_publish_failed")

    logger.info(
        "sismo_forward_done",
        extra={"forwarded": forwarded, "status": resp.status_code, "phone": phone[-4:]},
    )
    return {"forwarded": forwarded, "sismo_status": resp.status_code}
