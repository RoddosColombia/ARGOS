"""Tests de los endpoints /api/v1/social/accounts y /posts."""
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
    accounts = [
        {
            "workspace_id": "RODDOS",
            "plataforma": "tiktok" if i % 2 == 0 else "ig",
            "username": f"vendor_{i}",
            "seguidores": 100_000 - i * 1000,
            "engagement_rate": 5.0 - i * 0.1,
            "descripcion": f"Cuenta de prueba {i}",
            "url_perfil": f"https://example.com/{i}",
            "relevancia_score": 90.0 - i * 0.5,
            "fuente_query": "aceite moto",
            "ultima_metricas_at": now,
            "created_at": now,
            "updated_at": now,
        }
        for i in range(5)
    ]
    posts = [
        {
            "workspace_id": "RODDOS",
            "plataforma": "tiktok",
            "username": f"vendor_{i}",
            "post_external_id": f"post_{i}",
            "url_post": f"https://tiktok.com/@vendor_{i}/post_{i}",
            "descripcion": f"Post viral {i}",
            "vistas": 200_000 - i * 10_000,
            "likes": 5000,
            "comentarios": 100,
            "hashtags": ["moto", "repuestos"],
            "fecha_publicacion": now - timedelta(hours=i),
            "viral_flag": True,
            "created_at": now,
            "updated_at": now,
        }
        for i in range(5)
    ]
    await db[col.SOCIAL_ACCOUNTS].insert_many(accounts)
    await db[col.SOCIAL_POSTS].insert_many(posts)
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


async def test_endpoint_accounts_devuelve_top_ordenado_por_relevancia(
    seeded_db: AsyncIOMotorDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = {"Authorization": f"Bearer {_ceo_token()}", "X-Workspace-Id": "RODDOS"}
    async for client in _authed_client(monkeypatch):
        resp = await client.get("/api/v1/social/accounts?limit=10", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body) == 5
        # Schema correcto
        for key in ("plataforma", "username", "seguidores", "engagement_rate", "relevancia_score"):
            assert key in body[0]
        # Sort por relevancia desc
        scores = [a["relevancia_score"] for a in body]
        assert scores == sorted(scores, reverse=True)


async def test_endpoint_posts_devuelve_ordenado_por_vistas_desc(
    seeded_db: AsyncIOMotorDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = {"Authorization": f"Bearer {_ceo_token()}", "X-Workspace-Id": "RODDOS"}
    async for client in _authed_client(monkeypatch):
        resp = await client.get("/api/v1/social/posts?limit=10", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body) == 5
        # Schema
        for key in ("plataforma", "username", "post_external_id", "vistas", "likes", "hashtags"):
            assert key in body[0]
        # Sort por vistas desc
        vistas = [p["vistas"] for p in body]
        assert vistas == sorted(vistas, reverse=True)
        assert vistas[0] == 200_000
