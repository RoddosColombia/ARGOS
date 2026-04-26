"""Tests de /api/v1/recommendations · list + hit-rate + approve + reject."""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from argos.auth.security import create_access_token
from argos.config import get_settings
from argos.db import collections as col
from argos.db.indexes import ensure_indexes
from argos.main import create_app
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from tests.backend.test_integration_mongo import REAL_URI

pytestmark = pytest.mark.skipif(
    not REAL_URI,
    reason="MONGODB_URI no disponible · integration tests saltados",
)


@pytest_asyncio.fixture
async def seeded_db() -> AsyncIterator[AsyncIOMotorDatabase]:
    client = AsyncIOMotorClient(REAL_URI, serverSelectionTimeoutMS=5000)
    db = client[os.environ.get("MONGODB_TEST_DATABASE", "argos_test")]
    for c in col.ALL_KNOWN:
        await db[c].drop()
    await ensure_indexes(db)

    now = datetime.now(tz=UTC)
    pendiente_id = ObjectId()
    evaluada_id = ObjectId()
    await db[col.RECOMMENDATIONS].insert_many(
        [
            {
                "_id": pendiente_id,
                "workspace_id": "RODDOS",
                "briefing_id": "b1",
                "accion_index": 0,
                "type": "pricing_change",
                "action_description": "Bajar Motul",
                "rationale": "competencia",
                "expected_impact": {"metric": "qualitative", "target": "share", "confidence": 0.7},
                "actual_impact": None,
                "hit_rate_contribution": None,
                "learning": None,
                "priority": "Alta",
                "priority_score": 0.9,
                "status": "pendiente",
                "fecha_briefing": now.strftime("%Y-%m-%d"),
                "shown_in_briefing": [now.strftime("%Y-%m-%d")],
                "created_at": now,
                "updated_at": now,
            },
            {
                "_id": evaluada_id,
                "workspace_id": "RODDOS",
                "briefing_id": "b0",
                "accion_index": 0,
                "type": "pricing_change",
                "action_description": "Subir aceite Castrol",
                "rationale": "demanda alta",
                "expected_impact": {"metric": "qualitative", "target": "+5% margen", "confidence": 0.6},
                "actual_impact": {"metric": "qualitative", "valor_real": "1.0", "medido_at": now},
                "hit_rate_contribution": 1.0,
                "learning": "Funcionó · timing correcto.",
                "priority": "Media",
                "priority_score": 0.6,
                "status": "evaluada",
                "fecha_briefing": (now - timedelta(days=14)).strftime("%Y-%m-%d"),
                "shown_in_briefing": [(now - timedelta(days=14)).strftime("%Y-%m-%d")],
                "executed_at": now - timedelta(days=10),
                "evaluated_at": now - timedelta(days=2),
                "created_at": now - timedelta(days=14),
                "updated_at": now - timedelta(days=2),
            },
            # workspace ajeno · no debe aparecer en queries
            {
                "workspace_id": "OTRO",
                "briefing_id": "x",
                "accion_index": 0,
                "type": "pricing_change",
                "action_description": "Tóxica · workspace ajeno",
                "rationale": "—",
                "expected_impact": {},
                "priority": "Alta",
                "priority_score": 0.9,
                "status": "pendiente",
                "fecha_briefing": now.strftime("%Y-%m-%d"),
                "shown_in_briefing": [],
                "created_at": now,
                "updated_at": now,
            },
        ]
    )
    try:
        yield db
    finally:
        for c in col.ALL_KNOWN:
            await db[c].drop()
        client.close()


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


async def test_list_recommendations_filtra_workspace_y_ordena(
    seeded_db: AsyncIOMotorDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = {"Authorization": f"Bearer {_ceo_token()}", "X-Workspace-Id": "RODDOS"}
    async for client in _authed_client(monkeypatch):
        resp = await client.get("/api/v1/recommendations?limit=10", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # 2 docs RODDOS · 0 cross-workspace
        assert len(body) == 2
        # Ordenado por priority_score desc · Alta primero
        assert body[0]["priority"] == "Alta"
        assert "Tóxica" not in resp.text


async def test_hit_rate_promedia_evaluadas(
    seeded_db: AsyncIOMotorDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = {"Authorization": f"Bearer {_ceo_token()}", "X-Workspace-Id": "RODDOS"}
    async for client in _authed_client(monkeypatch):
        resp = await client.get("/api/v1/recommendations/hit-rate?days=30", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["evaluated_count"] == 1
        assert body["avg_hit_rate"] == 1.0


async def test_approve_actualiza_status_y_emite_evento(
    seeded_db: AsyncIOMotorDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = {"Authorization": f"Bearer {_ceo_token()}", "X-Workspace-Id": "RODDOS"}
    pendiente = await seeded_db[col.RECOMMENDATIONS].find_one(
        {"workspace_id": "RODDOS", "status": "pendiente"}
    )
    rec_id = str(pendiente["_id"])

    async for client in _authed_client(monkeypatch):
        resp = await client.post(f"/api/v1/recommendations/{rec_id}/approve", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "aprobada"
        assert body["approved_by"] == "ceo@roddos.com"

    # Doc actualizado
    doc = await seeded_db[col.RECOMMENDATIONS].find_one({"_id": pendiente["_id"]})
    assert doc["status"] == "aprobada"

    # Evento emitido
    event = await seeded_db[col.ARGOS_EVENTS].find_one(
        {"event_type": "recommendation.approved"}
    )
    assert event is not None
    assert event["payload"]["recommendation_id"] == rec_id


async def test_reject_actualiza_status_con_reason(
    seeded_db: AsyncIOMotorDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = {"Authorization": f"Bearer {_ceo_token()}", "X-Workspace-Id": "RODDOS"}
    pendiente = await seeded_db[col.RECOMMENDATIONS].find_one(
        {"workspace_id": "RODDOS", "status": "pendiente"}
    )
    rec_id = str(pendiente["_id"])

    async for client in _authed_client(monkeypatch):
        resp = await client.post(
            f"/api/v1/recommendations/{rec_id}/reject",
            headers=headers,
            json={"reason": "Margen no permite bajar más"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "rechazada"

    doc = await seeded_db[col.RECOMMENDATIONS].find_one({"_id": pendiente["_id"]})
    assert doc["status"] == "rechazada"
    assert doc["rejected_reason"] == "Margen no permite bajar más"

    event = await seeded_db[col.ARGOS_EVENTS].find_one(
        {"event_type": "recommendation.rejected"}
    )
    assert event is not None
    assert "Margen" in event["payload"]["reason"]
