"""NotificationsAgent · WhatsApp delivery del Morning Briefing + price alerts.

- `send_briefing_whatsapp(briefing)` · llamado por Executive después de
  `publish_briefing` · formatea las 3 acciones del día y manda al CEO.
- `notify_recent_price_alerts(db)` · job recurrente · busca eventos
  `marketplace.price.alert` con `delta_pct ≤ -15` en la última hora y manda
  WhatsApp por cada uno (deduplicado vía marca `whatsapp_notified` en el evento).

Skip silencioso si Twilio no está configurado (no se rompe el pipeline).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.agents.strategist.service import MorningBriefing
from argos.config import get_settings
from argos.db import collections as col
from argos.partners.twilio.client import TwilioError, TwilioWhatsAppClient

logger = logging.getLogger("argos.agents.notifications")

DEFAULT_DROP_THRESHOLD_PCT = -15.0
ALERT_LOOKBACK_MINUTES = 60


class NotificationsAgent:
    """Wrapper de alto nivel sobre `TwilioWhatsAppClient`."""

    def __init__(self, client: TwilioWhatsAppClient | None = None) -> None:
        if client is None:
            settings = get_settings()
            client = TwilioWhatsAppClient(
                account_sid=settings.twilio_account_sid,
                auth_token=settings.twilio_auth_token,
                whatsapp_from=settings.twilio_whatsapp_from,
                whatsapp_to=settings.twilio_whatsapp_to,
            )
        self._client = client

    @property
    def enabled(self) -> bool:
        return self._client.enabled

    async def send(self, body: str, *, to: str = "") -> dict[str, Any]:
        async with self._client:
            return await self._client.send_whatsapp(body, to=to)


def format_briefing_text(briefing: MorningBriefing) -> str:
    """Formatea el briefing en texto plano de WhatsApp · ≤1600 chars."""
    lines = [
        f"☕ Morning Briefing · {briefing.fecha}",
        "",
        f"Mercado 24h · {briefing.mercado_24h.nuevos_skus} nuevos SKUs · "
        f"{briefing.mercado_24h.bajas_precio} bajas · "
        f"{briefing.mercado_24h.nuevas_promos} promos",
        "",
    ]
    if briefing.acciones_del_dia:
        lines.append("Acciones del día:")
        for i, accion in enumerate(briefing.acciones_del_dia[:3], start=1):
            lines.append(
                f"{i}. [{accion.prioridad}] {accion.accion}"
            )
            if accion.justificacion:
                lines.append(f"   Por qué: {accion.justificacion[:120]}")
    else:
        lines.append("Sin acciones recomendadas hoy.")

    lines.append("")
    if briefing.estado_mercado:
        lines.append(briefing.estado_mercado[:300])
    return "\n".join(lines)


async def send_briefing_whatsapp(
    briefing: MorningBriefing,
    *,
    agent: NotificationsAgent | None = None,
) -> dict[str, Any]:
    """Envía el briefing por WhatsApp · skip silencioso sin Twilio."""
    if agent is None:
        agent = NotificationsAgent()
    if not agent.enabled:
        logger.warning("briefing_whatsapp_skipped_no_twilio")
        return {"sent": False, "reason": "no_twilio_configured"}
    text = format_briefing_text(briefing)
    try:
        result = await agent.send(text)
    except TwilioError as exc:
        logger.exception("briefing_whatsapp_failed", extra={"twilio_status": exc.status})
        return {"sent": False, "reason": f"twilio_{exc.status}"}
    sid = result.get("sid", "")
    logger.info("briefing_whatsapp_sent", extra={"twilio_sid": sid})
    return {"sent": True, "twilio_sid": sid}


def format_price_alert(payload: dict[str, Any]) -> str:
    """Formatea evento `marketplace.price.alert` para WhatsApp."""
    sku = payload.get("sku_normalizado", "—")
    delta = float(payload.get("delta_pct", 0))
    nuevo = float(payload.get("precio_actual", 0))
    anterior = float(payload.get("precio_anterior", 0))
    fuente = payload.get("fuente", "marketplace")
    titulo = payload.get("titulo", "")[:80]
    return (
        f"⚠️ ARGOS · Alerta precio\n"
        f"{titulo or sku} bajó {abs(delta):.1f}% en {fuente.upper()}\n"
        f"Nuevo: ${nuevo:,.0f} (antes ${anterior:,.0f})"
    )


async def notify_recent_price_alerts(
    db: AsyncIOMotorDatabase,
    *,
    workspace_id: str = "RODDOS",
    threshold_pct: float = DEFAULT_DROP_THRESHOLD_PCT,
    lookback_minutes: int = ALERT_LOOKBACK_MINUTES,
    agent: NotificationsAgent | None = None,
) -> dict[str, int]:
    """Job: lee eventos `marketplace.price.alert` recientes con drop fuerte y manda WhatsApp.

    Deduplicación: marca cada evento procesado con `metadata.whatsapp_notified=True`
    (mutación SOLO de metadata · NO viola ROG-A6 que es sobre payload immutability).
    """
    if agent is None:
        agent = NotificationsAgent()
    if not agent.enabled:
        logger.warning("price_alerts_whatsapp_skipped_no_twilio")
        return {"checked": 0, "sent": 0, "errors": 0}

    cutoff = datetime.now(tz=UTC) - timedelta(minutes=lookback_minutes)
    cursor = db[col.ARGOS_EVENTS].find({
        "workspace_id": workspace_id,
        "event_type": "marketplace.price.alert",
        "timestamp_utc": {"$gte": cutoff},
        "payload.delta_pct": {"$lte": threshold_pct},
        "metadata.whatsapp_notified": {"$ne": True},
    }).limit(20)
    events = await cursor.to_list(length=20)

    sent = 0
    errors = 0
    for ev in events:
        text = format_price_alert(ev.get("payload") or {})
        try:
            await agent.send(text)
            sent += 1
            await db[col.ARGOS_EVENTS].update_one(
                {"_id": ev["_id"]},
                {"$set": {
                    "metadata.whatsapp_notified": True,
                    "metadata.whatsapp_notified_at": datetime.now(tz=UTC),
                }},
            )
        except TwilioError:
            logger.exception("price_alert_whatsapp_failed", extra={"event_id": ev.get("event_id")})
            errors += 1

    logger.info(
        "price_alerts_whatsapp_done",
        extra={"checked": len(events), "sent": sent, "errors": errors},
    )
    return {"checked": len(events), "sent": sent, "errors": errors}
