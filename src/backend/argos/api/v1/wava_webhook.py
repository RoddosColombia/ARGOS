"""Wava webhook receiver · recibe eventos de pago (Build 3.3 · Capa 1).

POST /api/v1/wava/webhook recibe notificaciones de Wava (order.confirmed,
order.failed, order.cancelled, order.refunded).

Seguridad: Wava NO envía HMAC. Verificamos status llamando GET /v1/orders/{id}
antes de procesar. Idempotente por wava_order_id en wava_orders.

Refs: phase_3/build_3.3 · ROG-A12 (audit) · ROG-A1 (dinero = humano)
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse

from argos.config import get_settings
from argos.db import collections as col
from argos.db.mongo import get_mongo_client
from argos.partners.wava.client import WavaClient
from argos.services.audit import ActionResult, ActorType, audit_write

logger = logging.getLogger("argos.api.v1.wava_webhook")

router = APIRouter(prefix="/api/v1/wava", tags=["wava"])


async def _process_webhook(payload: dict[str, Any]) -> None:
    """Procesa el webhook en background después de responder 200."""
    settings = get_settings()
    client = get_mongo_client()
    if client is None:
        logger.warning("wava_webhook_no_db")
        return

    db = client[settings.mongodb_database]
    workspace_id = "RODDOS"

    event_type = payload.get("event", payload.get("type", ""))
    order_data = payload.get("data", payload.get("order", payload))
    wava_order_id = str(
        order_data.get("id", order_data.get("order_id", ""))
    )

    if not wava_order_id:
        logger.warning("wava_webhook_no_order_id", extra={"payload_keys": list(payload.keys())[:10]})
        return

    await audit_write(
        db,
        workspace_id=workspace_id,
        actor_type=ActorType.SYSTEM,
        actor_id="wava_webhook",
        action="wava.webhook.received",
        resource_type="wava_order",
        resource_id=wava_order_id,
        result=ActionResult.SUCCESS,
        metadata={"event_type": event_type, "wava_order_id": wava_order_id},
    )

    verified_status = ""
    async with WavaClient(
        merchant_key=settings.wava_merchant_key,
        base_url=settings.wava_api_url,
    ) as wava:
        if wava.enabled:
            try:
                verified_order = await wava.get_order(wava_order_id)
                verified_status = verified_order.status
            except Exception:  # noqa: BLE001
                logger.exception("wava_webhook_verify_failed", extra={"wava_order_id": wava_order_id})
                return
        else:
            logger.warning("wava_webhook_no_merchant_key_cannot_verify")
            return

    if not verified_status:
        logger.warning("wava_webhook_empty_verified_status", extra={"wava_order_id": wava_order_id})
        return

    now = datetime.now(tz=UTC)
    update_fields: dict[str, Any] = {
        "status": verified_status,
        "updated_at": now,
    }

    if verified_status == "confirmed":
        update_fields["wava_confirmed_at"] = now
    elif verified_status in ("failed", "cancelled", "refunded"):
        update_fields[f"wava_{verified_status}_at"] = now

    result = await db[col.WAVA_ORDERS].update_one(
        {"workspace_id": workspace_id, "wava_order_id": wava_order_id},
        {"$set": update_fields},
    )

    if result.matched_count == 0:
        logger.warning(
            "wava_webhook_order_not_found",
            extra={"wava_order_id": wava_order_id, "verified_status": verified_status},
        )
        return

    event_map = {
        "confirmed": "wava.payment.confirmed",
        "failed": "wava.payment.failed",
        "cancelled": "wava.payment.cancelled",
        "refunded": "wava.payment.refunded",
    }
    bus_event = event_map.get(verified_status)
    if bus_event:
        from argos.db.events import publish_event
        try:
            await publish_event(
                db,
                event_type=bus_event,
                workspace_id=workspace_id,
                producer="wava_webhook",
                payload={
                    "wava_order_id": wava_order_id,
                    "verified_status": verified_status,
                },
            )
        except Exception:  # noqa: BLE001
            logger.exception("wava_webhook_event_publish_failed")

    await audit_write(
        db,
        workspace_id=workspace_id,
        actor_type=ActorType.SYSTEM,
        actor_id="wava_webhook",
        action="wava.webhook.processed",
        resource_type="wava_order",
        resource_id=wava_order_id,
        result=ActionResult.SUCCESS,
        metadata={"verified_status": verified_status, "matched": result.matched_count},
    )

    logger.info(
        "wava_webhook_processed",
        extra={"wava_order_id": wava_order_id, "verified_status": verified_status},
    )


@router.post("/webhook")
async def wava_webhook(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    """Recibe webhook de Wava. Responde 200 inmediatamente (<5 seg)."""
    try:
        payload: dict[str, Any] = await request.json()
    except Exception:  # noqa: BLE001
        logger.warning("wava_webhook_invalid_json")
        return JSONResponse(status_code=200, content={"received": True})

    background_tasks.add_task(_process_webhook, payload)
    return JSONResponse(status_code=200, content={"received": True})
