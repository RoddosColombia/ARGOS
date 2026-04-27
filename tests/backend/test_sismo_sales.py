"""Tests del SismoAgent ventas diarias + endpoint /sismo/sales · Build 4.2."""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
import pytest_asyncio
from argos.agents.sismo.service import (
    SismoAgent,
    sync_sismo_sales_daily_job,
)
from argos.agents.strategist.impact import evaluate_pending_recommendations
from argos.auth.security import create_access_token
from argos.config import get_settings
from argos.db import collections as col
from argos.db.indexes import ensure_indexes
from argos.main import create_app
from argos.partners.sismo.client import SismoClient
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from tests.backend.test_integration_mongo import REAL_URI

pytestmark = pytest.mark.skipif(
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


def _mock_sales_client(items: list[dict[str, Any]]) -> SismoClient:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=items)

    client = SismoClient(base_url="https://sismo.test", api_key="key-test")
    transport = httpx.MockTransport(handler)
    client._client = httpx.AsyncClient(transport=transport, base_url="https://sismo.test")
    return client


async def test_sales_sync_persiste_y_emite_evento(
    indexed_db: AsyncIOMotorDatabase,
) -> None:
    items = [
        {"sku": "FRENO-001", "units_sold": 5, "revenue": 225000, "channel": "tienda"},
        {"sku": "ACEITE-002", "units_sold": 3, "revenue": 156000, "channel": "whatsapp"},
    ]
    fake_client = _mock_sales_client(items)
    agent = SismoAgent(client=fake_client)

    stats = await sync_sismo_sales_daily_job(
        indexed_db, workspace_id="RODDOS", fecha="2026-04-25", agent=agent
    )

    assert stats.enabled is True
    assert stats.fecha == "2026-04-25"
    assert stats.sales_count == 2
    assert stats.units_total == 8
    assert stats.revenue_total == 381000
    assert stats.inserted == 2

    # Idempotente: re-run del mismo día no duplica
    stats2 = await sync_sismo_sales_daily_job(
        indexed_db, workspace_id="RODDOS", fecha="2026-04-25", agent=agent
    )
    assert stats2.inserted == 0
    count = await indexed_db[col.SISMO_SALES_DAILY].count_documents(
        {"workspace_id": "RODDOS", "date": "2026-04-25"}
    )
    assert count == 2

    # Evento emitido
    event = await indexed_db[col.ARGOS_EVENTS].find_one(
        {"event_type": "sismo.sales.daily.synced"}
    )
    assert event is not None
    assert event["payload"]["sales_count"] == 2
    assert event["payload"]["units_total"] == 8


async def test_sales_sync_skip_silencioso_sin_credenciales(
    indexed_db: AsyncIOMotorDatabase,
) -> None:
    agent = SismoAgent(client=SismoClient(base_url="", api_key=""))
    stats = await sync_sismo_sales_daily_job(
        indexed_db, workspace_id="RODDOS", fecha="2026-04-25", agent=agent
    )
    assert stats.enabled is False
    count = await indexed_db[col.SISMO_SALES_DAILY].count_documents({"workspace_id": "RODDOS"})
    assert count == 0


def _ceo_token() -> str:
    return create_access_token(subject="ceo@roddos.com", role="ceo", workspace_id="RODDOS")


async def _authed_client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setenv("MONGODB_URI", REAL_URI)
    monkeypatch.setenv("MONGODB_DATABASE", os.environ.get("MONGODB_TEST_DATABASE", "argos_test"))
    monkeypatch.setenv("ARGOS_DISABLE_SCHEDULER", "true")
    get_settings.cache_clear()
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        yield client
    get_settings.cache_clear()


async def test_endpoint_sales_filtra_por_fecha_y_sku(
    indexed_db: AsyncIOMotorDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    items = [
        {"sku": "A", "units_sold": 10, "revenue": 100000, "channel": "tienda"},
        {"sku": "B", "units_sold": 2, "revenue": 50000, "channel": "whatsapp"},
    ]
    agent = SismoAgent(client=_mock_sales_client(items))
    await sync_sismo_sales_daily_job(
        indexed_db, workspace_id="RODDOS", fecha="2026-04-25", agent=agent
    )

    headers = {"Authorization": f"Bearer {_ceo_token()}", "X-Workspace-Id": "RODDOS"}
    async for client in _authed_client(monkeypatch):
        # Sin date → último disponible
        resp = await client.get("/api/v1/sismo/sales", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["date"] == "2026-04-25"
        assert body["totals"]["count"] == 2
        assert body["totals"]["units_sold"] == 12

        # Filtro por SKU
        resp_sku = await client.get(
            "/api/v1/sismo/sales?date=2026-04-25&sku=A", headers=headers
        )
        body_sku = resp_sku.json()
        assert body_sku["totals"]["count"] == 1
        assert body_sku["items"][0]["sku"] == "A"


class _FakeAnthropicClient:
    def __init__(self) -> None:
        self.messages = self

    async def create(self, **_kwargs):  # noqa: ANN003
        class _Block:
            text = "Vendieron 10 unidades en 7d · funcionó."

        class _Resp:
            content = [_Block()]

        return _Resp()


async def test_impact_tracker_usa_ventas_reales_para_pricing_change(
    indexed_db: AsyncIOMotorDatabase,
) -> None:
    """Build 4.2: actual_impact se llena con units_sold + revenue_cop reales."""
    now = datetime.now(tz=UTC)
    executed_at = now - timedelta(days=10)

    rec_id = ObjectId()
    await indexed_db[col.RECOMMENDATIONS].insert_one(
        {
            "_id": rec_id,
            "workspace_id": "RODDOS",
            "briefing_id": "b-impact-sales",
            "accion_index": 0,
            "type": "pricing_change",
            "action_description": "Bajar precio Aceite Motul",
            "rationale": "competencia",
            "expected_impact": {"metric": "qualitative", "target": "share", "confidence": 0.7},
            "actual_impact": None,
            "hit_rate_contribution": None,
            "learning": None,
            "priority": "Alta",
            "priority_score": 0.9,
            "status": "ejecutada",
            "fecha_briefing": executed_at.strftime("%Y-%m-%d"),
            "shown_in_briefing": [executed_at.strftime("%Y-%m-%d")],
            "executed_at": executed_at,
            "created_at": executed_at,
            "updated_at": executed_at,
        }
    )

    # Poblar sismo_sales_daily en la ventana 7d post-ejecución
    for offset in range(7):
        d = (executed_at + timedelta(days=offset)).strftime("%Y-%m-%d")
        await indexed_db[col.SISMO_SALES_DAILY].insert_one(
            {
                "workspace_id": "RODDOS",
                "date": d,
                "sku": "ACEITE-MOTUL",
                "units_sold": 4,
                "revenue": 200000,
                "channel": "tienda",
                "fecha_sync": now,
                "created_at": now,
                "updated_at": now,
            }
        )

    fake = _FakeAnthropicClient()
    stats = await evaluate_pending_recommendations(
        indexed_db, workspace_id="RODDOS", anthropic_client=fake
    )
    assert stats["evaluated"] == 1

    doc = await indexed_db[col.RECOMMENDATIONS].find_one({"_id": rec_id})
    assert doc["status"] == "evaluada"
    assert doc["actual_impact"]["metric"] == "units_sold_and_revenue"
    assert doc["actual_impact"]["units_sold"] == 28  # 4 * 7
    assert doc["actual_impact"]["revenue_cop"] == 1400000.0
    assert doc["actual_impact"]["days_with_data"] == 7
