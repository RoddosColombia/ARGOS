"""Tests del job de impact evaluation · heurística + mock Sonnet."""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from argos.agents.strategist.impact import (
    _heuristic_hit_rate,
    evaluate_pending_recommendations,
)
from argos.db import collections as col
from argos.db.indexes import ensure_indexes
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from tests.backend.test_integration_mongo import REAL_URI


def test_heuristic_pricing_change_bajar_con_evidencia() -> None:
    rec = {"type": "pricing_change", "action_description": "Bajar precio de aceite Motul a $52K"}
    events = [
        {"event_type": "marketplace.price.changed", "payload": {"delta_pct": -8.0}},
        {"event_type": "marketplace.price.changed", "payload": {"delta_pct": -5.0}},
    ]
    assert _heuristic_hit_rate(rec, events) == 1.0


def test_heuristic_pricing_change_sin_eventos() -> None:
    rec = {"type": "pricing_change", "action_description": "Subir precio de pastilla freno"}
    assert _heuristic_hit_rate(rec, []) == 0.0


def test_heuristic_default_para_otros_tipos() -> None:
    rec = {"type": "promo_launch", "action_description": "Activar promo aceite Castrol"}
    assert _heuristic_hit_rate(rec, []) == 0.5


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


class _FakeAnthropicClient:
    """Mock de anthropic.AsyncAnthropic.messages.create."""

    def __init__(self) -> None:
        self.messages = self  # imita atributo .messages

    async def create(self, **_kwargs):  # noqa: ANN003
        class _Block:
            text = "Funcionó porque la competencia bajó antes y nosotros igualamos en 24h."

        class _Resp:
            content = [_Block()]

        return _Resp()


@pytestmark_integration
async def test_evaluate_pending_recommendations_actualiza_y_emite_evento(
    indexed_db: AsyncIOMotorDatabase,
) -> None:
    now = datetime.now(tz=UTC)
    executed_at = now - timedelta(days=10)

    rec_id = ObjectId()
    await indexed_db[col.RECOMMENDATIONS].insert_one(
        {
            "_id": rec_id,
            "workspace_id": "RODDOS",
            "briefing_id": "b-impact-1",
            "accion_index": 0,
            "type": "pricing_change",
            "action_description": "Bajar precio Motul a 52K",
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

    # Evento de evidencia dentro de la ventana 7d post-ejecución
    await indexed_db[col.ARGOS_EVENTS].insert_one(
        {
            "event_id": "evt_test_1",
            "event_type": "marketplace.price.changed",
            "version": "1.0",
            "workspace_id": "RODDOS",
            "timestamp_utc": executed_at + timedelta(days=2),
            "producer": "marketplace_agent",
            "payload": {"delta_pct": -8.5},
            "metadata": {},
        }
    )

    fake = _FakeAnthropicClient()
    stats = await evaluate_pending_recommendations(
        indexed_db, workspace_id="RODDOS", anthropic_client=fake
    )
    assert stats["evaluated"] == 1
    assert stats["errors"] == 0

    doc = await indexed_db[col.RECOMMENDATIONS].find_one({"_id": rec_id})
    assert doc["status"] == "evaluada"
    assert doc["hit_rate_contribution"] == 1.0
    assert "Funcionó" in doc["learning"]
    assert doc["actual_impact"]["valor_real"] == "1.0"

    event = await indexed_db[col.ARGOS_EVENTS].find_one(
        {"event_type": "recommendation.evaluated"}
    )
    assert event is not None
    assert event["payload"]["hit_rate_contribution"] == 1.0
