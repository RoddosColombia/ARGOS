"""Tests del config API · queries CRUD + categories + suggestions."""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime

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
    await db[col.CATEGORIES].insert_many([
        {
            "workspace_id": "RODDOS",
            "slug": "repuestos_moto",
            "label": "Repuestos para moto",
            "active": True,
            "created_at": now,
        },
        {
            "workspace_id": "RODDOS",
            "slug": "accesorios_moto",
            "label": "Accesorios para moto",
            "active": False,
            "created_at": now,
        },
    ])
    await db[col.DISCOVERY_SUGGESTIONS].insert_one(
        {
            "_id": ObjectId(),
            "workspace_id": "RODDOS",
            "category": "repuestos_moto",
            "term": "casco modular smart",
            "signal_type": "trending",
            "confidence": 0.82,
            "evidence": {"metric": "product_mentions_7d", "value": 12, "delta_pct": None},
            "date": now.strftime("%Y-%m-%d"),
            "status": "pending",
            "created_at": now,
        }
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


async def test_queries_crud_completo(
    seeded_db: AsyncIOMotorDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = {"Authorization": f"Bearer {_ceo_token()}", "X-Workspace-Id": "RODDOS"}
    async for client in _authed_client(monkeypatch):
        # POST: crear query manual
        resp = await client.post(
            "/api/v1/config/queries",
            headers=headers,
            json={
                "query": "kit arrastre Pulsar 200",
                "category": "repuestos_moto",
                "priority": 3,
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["origin"] == "manual"
        assert body["status"] == "active"
        qid = body["id"]

        # GET: lista incluye la query nueva
        resp = await client.get("/api/v1/config/queries?status=active", headers=headers)
        assert resp.status_code == 200
        items = resp.json()
        assert any(q["id"] == qid for q in items)

        # PATCH: pausa la query
        resp = await client.patch(
            f"/api/v1/config/queries/{qid}",
            headers=headers,
            json={"status": "paused"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "paused"
        # Legacy `activa` sync'd
        doc = await seeded_db[col.WATCH_QUERIES].find_one({"_id": ObjectId(qid)})
        assert doc["activa"] is False

        # DELETE
        resp = await client.delete(f"/api/v1/config/queries/{qid}", headers=headers)
        assert resp.status_code == 204
        doc = await seeded_db[col.WATCH_QUERIES].find_one({"_id": ObjectId(qid)})
        assert doc is None


async def test_categories_toggle(
    seeded_db: AsyncIOMotorDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = {"Authorization": f"Bearer {_ceo_token()}", "X-Workspace-Id": "RODDOS"}
    async for client in _authed_client(monkeypatch):
        # El lifespan dispara seed que añade defaults · combinado con la fixture
        # pre-existente, esperamos al menos las 2 que la fixture sembró.
        resp = await client.get("/api/v1/config/categories", headers=headers)
        body = resp.json()
        assert len(body) >= 2
        accesorios = next(c for c in body if c["slug"] == "accesorios_moto")
        assert accesorios["active"] is False

        resp = await client.patch(
            "/api/v1/config/categories/accesorios_moto",
            headers=headers,
            json={"active": True},
        )
        assert resp.status_code == 200
        assert resp.json()["active"] is True


async def test_accept_suggestion_crea_watch_query(
    seeded_db: AsyncIOMotorDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = {"Authorization": f"Bearer {_ceo_token()}", "X-Workspace-Id": "RODDOS"}
    async for client in _authed_client(monkeypatch):
        resp = await client.get("/api/v1/config/suggestions?status=pending", headers=headers)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        sid = items[0]["id"]

        # Accept → crea watch_query con origin='suggested'
        resp = await client.post(
            f"/api/v1/config/suggestions/{sid}/accept",
            headers=headers,
            json={"source": "all"},
        )
        assert resp.status_code == 200
        assert resp.json()["accepted"] is True

    # Verificación post: watch_query existe con origin='suggested'
    wq = await seeded_db[col.WATCH_QUERIES].find_one(
        {"workspace_id": "RODDOS", "query": "casco modular smart"}
    )
    assert wq is not None
    assert wq["origin"] == "suggested"
    sugg = await seeded_db[col.DISCOVERY_SUGGESTIONS].find_one({"_id": ObjectId(sid)})
    assert sugg["status"] == "accepted"
