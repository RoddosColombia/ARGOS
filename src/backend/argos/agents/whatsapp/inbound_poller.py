"""Inbound poller · poll Mercately per-phone para mensajes nuevos (Build 3.1).

Flujo cada MERCATELY_POLL_INTERVAL_S (default 30s):
1. Lee phones activos de collection ``contacts`` (opt-in registrado).
2. Por cada phone, GET conversations desde Mercately.
3. Filtra mensajes inbound con timestamp > last_seen.
4. Persiste last_seen en ``mercately_polling_state``.
5. Pasa mensajes nuevos al IntentClassifier.
6. Si route_to="sismo", reenvía a SISMO vía SismoForwarder.

Refs: phase_3/build_3.1 · ROG-W1 (opt-in) · ROG-A3 (workspace_id)
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.agents.whatsapp.conversation_handler import handle_message
from argos.agents.whatsapp.intent_classifier import classify_intent
from argos.agents.whatsapp.sismo_forwarder import forward_to_sismo
from argos.db import collections as col
from argos.partners.mercately.client import MercatelyClient

logger = logging.getLogger("argos.agents.whatsapp.inbound_poller")


async def _get_active_phones(
    db: AsyncIOMotorDatabase,
    workspace_id: str,
) -> list[str]:
    """Lee phones con opt-in activo de la colección contacts."""
    cursor = db[col.CONTACTS].find(
        {"workspace_id": workspace_id, "opt_in_whatsapp": True},
        {"phone": 1, "_id": 0},
    )
    docs = await cursor.to_list(length=500)
    return [d["phone"] for d in docs if d.get("phone")]


async def _get_last_seen(
    db: AsyncIOMotorDatabase,
    phone: str,
    workspace_id: str,
) -> datetime | None:
    doc = await db[col.MERCATELY_POLLING_STATE].find_one(
        {"phone": phone, "workspace_id": workspace_id},
    )
    if doc and doc.get("last_seen_at"):
        return doc["last_seen_at"]
    return None


async def _update_last_seen(
    db: AsyncIOMotorDatabase,
    phone: str,
    workspace_id: str,
    last_seen_at: datetime,
) -> None:
    await db[col.MERCATELY_POLLING_STATE].update_one(
        {"phone": phone, "workspace_id": workspace_id},
        {
            "$set": {"last_seen_at": last_seen_at, "updated_at": datetime.now(tz=UTC)},
            "$setOnInsert": {"created_at": datetime.now(tz=UTC)},
        },
        upsert=True,
    )


def _extract_inbound_messages(
    conversations_response: dict[str, Any],
    after: datetime | None,
) -> list[dict[str, Any]]:
    """Extrae mensajes inbound (direction=in) más recientes que ``after``."""
    messages: list[dict[str, Any]] = []
    convos = conversations_response.get("data", conversations_response.get("conversations", []))
    if isinstance(convos, list):
        for convo in convos:
            msgs = convo.get("messages", [])
            if isinstance(msgs, list):
                for msg in msgs:
                    if msg.get("direction") != "in":
                        continue
                    msg_time_raw = msg.get("created_at") or msg.get("timestamp")
                    if not msg_time_raw:
                        continue
                    if isinstance(msg_time_raw, str):
                        try:
                            msg_time = datetime.fromisoformat(msg_time_raw.replace("Z", "+00:00"))
                        except ValueError:
                            continue
                    elif isinstance(msg_time_raw, datetime):
                        msg_time = msg_time_raw
                    else:
                        continue
                    if after and msg_time <= after:
                        continue
                    messages.append({**msg, "_parsed_time": msg_time})
    return sorted(messages, key=lambda m: m["_parsed_time"])


async def poll_inbound(
    db: AsyncIOMotorDatabase,
    *,
    mercately_client: MercatelyClient,
    workspace_id: str = "RODDOS",
    anthropic_api_key: str = "",
    sismo_webhook_url: str = "",
    webhook_secret: str = "",
    whatsapp_reply_enabled: bool = False,
) -> dict[str, int]:
    """Ejecuta un ciclo de polling completo.

    Retorna stats: {phones_checked, messages_found, classified, forwarded_sismo,
    responded_argos, errors}.
    """
    stats: dict[str, int] = {
        "phones_checked": 0,
        "messages_found": 0,
        "classified": 0,
        "forwarded_sismo": 0,
        "responded_argos": 0,
        "errors": 0,
    }

    if not mercately_client.enabled:
        logger.warning("inbound_poller_skipped_no_mercately")
        return stats

    phones = await _get_active_phones(db, workspace_id)
    stats["phones_checked"] = len(phones)

    for phone in phones:
        try:
            last_seen = await _get_last_seen(db, phone, workspace_id)
            response = await mercately_client.get_customer_messages(phone)
            if not response:
                continue

            new_msgs = _extract_inbound_messages(response, last_seen)
            stats["messages_found"] += len(new_msgs)

            latest_time: datetime | None = None
            for msg in new_msgs:
                msg_time: datetime = msg["_parsed_time"]
                text = msg.get("body") or msg.get("text") or ""
                if not text:
                    continue

                result = await classify_intent(
                    text,
                    phone=phone,
                    anthropic_api_key=anthropic_api_key,
                    db=db,
                    workspace_id=workspace_id,
                )
                stats["classified"] += 1

                if result.route_to == "sismo" and sismo_webhook_url:
                    await forward_to_sismo(
                        phone=phone,
                        message_text=text,
                        intent=result.intent,
                        confidence=result.confidence,
                        sismo_webhook_url=sismo_webhook_url,
                        webhook_secret=webhook_secret,
                        db=db,
                        workspace_id=workspace_id,
                    )
                    stats["forwarded_sismo"] += 1

                elif result.route_to == "argos" and whatsapp_reply_enabled:
                    await handle_message(
                        db,
                        classification=result,
                        message_text=text,
                        phone=phone,
                        mercately_client=mercately_client,
                        anthropic_api_key=anthropic_api_key,
                        workspace_id=workspace_id,
                    )
                    stats["responded_argos"] += 1

                if latest_time is None or msg_time > latest_time:
                    latest_time = msg_time

            if latest_time:
                await _update_last_seen(db, phone, workspace_id, latest_time)

        except Exception:  # noqa: BLE001
            logger.exception("inbound_poller_phone_error", extra={"phone": phone[-4:]})
            stats["errors"] += 1

    logger.info("inbound_poll_done", extra=stats)
    return stats
