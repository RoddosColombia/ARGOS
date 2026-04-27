"""Tests del NotificationsAgent · Twilio mock + briefing format + price alert flow."""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from argos.agents.notifications.service import (
    NotificationsAgent,
    format_briefing_text,
    format_price_alert,
    notify_recent_price_alerts,
    send_briefing_whatsapp,
)
from argos.agents.strategist.service import (
    AccionRecomendada,
    Mercado24h,
    MorningBriefing,
)
from argos.db import collections as col
from argos.db.indexes import ensure_indexes
from argos.partners.twilio.client import TwilioWhatsAppClient
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from tests.backend.test_integration_mongo import REAL_URI


def _briefing_fixture(fecha: str = "2026-04-27") -> MorningBriefing:
    return MorningBriefing(
        fecha=fecha,
        mercado_24h=Mercado24h(nuevos_skus=4, bajas_precio=2, nuevas_promos=1),
        acciones_del_dia=[
            AccionRecomendada(
                accion="Bajar Aceite Motul a $52K",
                justificacion="3 sellers MELI bajaron 22%",
                impacto_esperado="Recuperar share",
                prioridad="Alta",
            ),
            AccionRecomendada(
                accion="Stockear pastillas freno",
                justificacion="lunes pico",
                impacto_esperado="evitar stockout",
                prioridad="Media",
            ),
        ],
        estado_mercado="Día agresivo en aceites · respuesta requerida hoy.",
    )


def test_format_briefing_text_incluye_acciones_y_emoji() -> None:
    text = format_briefing_text(_briefing_fixture())
    assert "Morning Briefing" in text
    assert "2026-04-27" in text
    assert "Aceite Motul" in text
    assert "[Alta]" in text
    assert len(text) <= 1600


def _mock_twilio_client(*, status_code: int = 201) -> TwilioWhatsAppClient:
    """Crea un TwilioWhatsAppClient con httpx.MockTransport."""
    captured: dict[str, str] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = req.content.decode("utf-8")
        captured["url"] = str(req.url)
        return httpx.Response(status_code, json={"sid": "SM-test-12345"})

    client = TwilioWhatsAppClient(
        account_sid="AC-test",
        auth_token="auth",
        whatsapp_from="whatsapp:+14155238886",
        whatsapp_to="whatsapp:+573001234567",
    )
    transport = httpx.MockTransport(handler)
    client._client = httpx.AsyncClient(
        transport=transport,
        base_url="https://api.twilio.com/2010-04-01",
        auth=("AC-test", "auth"),
    )
    client._captured = captured  # type: ignore[attr-defined]
    return client


async def test_send_briefing_whatsapp_llama_twilio_y_devuelve_sid() -> None:
    fake = _mock_twilio_client()
    agent = NotificationsAgent(client=fake)
    result = await send_briefing_whatsapp(_briefing_fixture(), agent=agent)
    assert result["sent"] is True
    assert result["twilio_sid"] == "SM-test-12345"
    captured = fake._captured  # type: ignore[attr-defined]
    assert "Aceite+Motul" in captured["body"] or "Aceite%20Motul" in captured["body"]


async def test_send_briefing_whatsapp_skip_silencioso_sin_credenciales() -> None:
    agent = NotificationsAgent(
        client=TwilioWhatsAppClient(account_sid="", auth_token="", whatsapp_from="")
    )
    result = await send_briefing_whatsapp(_briefing_fixture(), agent=agent)
    assert result["sent"] is False
    assert result["reason"] == "no_twilio_configured"


pytestmark_integration = pytest.mark.skipif(
    not REAL_URI,
    reason="MONGODB_URI no disponible · integration tests saltados",
)


@pytest_asyncio.fixture
async def indexed_db() -> AsyncIterator[AsyncIOMotorDatabase]:
    client = AsyncIOMotorClient(REAL_URI, serverSelectionTimeoutMS=5000)
    db = client[os.environ.get("MONGODB_TEST_DATABASE", "argos_test")]
    for c in col.ALL_KNOWN:
        await db[c].drop()
    await ensure_indexes(db)
    try:
        yield db
    finally:
        for c in col.ALL_KNOWN:
            await db[c].drop()
        client.close()


@pytestmark_integration
async def test_notify_recent_price_alerts_dedupe_y_threshold(
    indexed_db: AsyncIOMotorDatabase,
) -> None:
    """Solo eventos con drop ≥ 15% se notifican · idempotente vs reruns."""
    now = datetime.now(tz=UTC)
    base = {
        "version": "1.0",
        "workspace_id": "RODDOS",
        "timestamp_utc": now - timedelta(minutes=10),
        "producer": "alerts_agent",
        "metadata": {},
    }
    await indexed_db[col.ARGOS_EVENTS].insert_many([
        {
            **base,
            "event_id": "evt_drop_critical",
            "event_type": "marketplace.price.alert",
            "payload": {
                "sku_normalizado": "ACEITE-001",
                "titulo": "Aceite Motul 4T",
                "precio_anterior": 60000,
                "precio_actual": 45000,
                "delta_pct": -25.0,
                "fuente": "meli",
                "competitor_url": "",
            },
        },
        {
            **base,
            "event_id": "evt_drop_minor",
            "event_type": "marketplace.price.alert",
            "payload": {
                "sku_normalizado": "BUJIA-001",
                "titulo": "Bujía NGK",
                "precio_anterior": 18000,
                "precio_actual": 17000,  # solo -5.5% · debajo del threshold
                "delta_pct": -5.5,
                "fuente": "meli",
                "competitor_url": "",
            },
        },
    ])

    agent = NotificationsAgent(client=_mock_twilio_client())
    stats = await notify_recent_price_alerts(indexed_db, workspace_id="RODDOS", agent=agent)
    assert stats["sent"] == 1  # solo el critical, no el minor
    assert stats["errors"] == 0

    # Segundo run: nada para enviar (ya marcado whatsapp_notified)
    stats2 = await notify_recent_price_alerts(indexed_db, workspace_id="RODDOS", agent=agent)
    assert stats2["checked"] == 0
    assert stats2["sent"] == 0


def test_format_price_alert_estructura_emoji() -> None:
    payload = {
        "sku_normalizado": "ACEITE-001",
        "titulo": "Aceite Motul 4T",
        "precio_anterior": 60000.0,
        "precio_actual": 45000.0,
        "delta_pct": -25.0,
        "fuente": "meli",
    }
    text = format_price_alert(payload)
    assert "⚠️" in text
    assert "ARGOS" in text
    assert "25.0%" in text
    assert "MELI" in text
    assert "$45,000" in text
