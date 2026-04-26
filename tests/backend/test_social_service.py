"""Tests del Social agent · TikHub mockeado."""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from argos.agents.social.service import (
    VIRAL_VIEWS_THRESHOLD,
    SocialAgent,
    parse_tikhub_account,
    parse_tikhub_post,
    refresh_social,
)
from argos.db import collections as col
from argos.db.indexes import ensure_indexes
from argos.partners.tikhub.client import TikHubClient
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


def test_parse_tikhub_account_normaliza_correctamente() -> None:
    raw = {
        "unique_id": "rappi_motos",
        "follower_count": 50_000,
        "total_favorited": 200_000,
        "aweme_count": 100,
        "signature": "Motos delivery #motos #pulsar",
        "share_url": "https://tiktok.com/@rappi_motos",
        "sec_uid": "MS4wLjABAAAA",
    }
    parsed = parse_tikhub_account(raw, platform="tiktok")
    assert parsed is not None
    assert parsed.username == "rappi_motos"
    assert parsed.seguidores == 50_000
    # avg_likes = 200K / 100 = 2K · engagement = 2000/50000 = 4%
    assert parsed.engagement_rate == 4.0
    assert parsed.descripcion.startswith("Motos delivery")
    assert parsed.sec_uid == "MS4wLjABAAAA"
    assert parsed.relevancia_score > 0


def test_parse_tikhub_account_devuelve_none_sin_username() -> None:
    assert parse_tikhub_account({}, platform="tiktok") is None
    assert parse_tikhub_account({"follower_count": 1000}, platform="ig") is None


def test_parse_tikhub_post_filtra_por_threshold_implicito() -> None:
    """parse_tikhub_post devuelve el post normalizado · el filtro viral está en SocialAgent."""
    raw_low = {
        "aweme_id": "post_low",
        "desc": "Aceite de moto #aceite",
        "statistics": {"play_count": 100, "digg_count": 5, "comment_count": 1},
        "create_time": 1714000000,
    }
    parsed = parse_tikhub_post(raw_low, platform="tiktok", username="alguien")
    assert parsed is not None
    assert parsed.vistas == 100
    assert parsed.likes == 5
    assert parsed.hashtags == ["aceite"]
    # No filtra · el agent decide si es viral
    assert parsed.vistas < VIRAL_VIEWS_THRESHOLD


def test_parse_tikhub_post_devuelve_none_sin_id() -> None:
    raw = {"desc": "sin id"}
    assert parse_tikhub_post(raw, platform="tiktok", username="x") is None


class _FakeTikHubClient(TikHubClient):
    """Mock que retorna respuestas configurables sin tocar red."""

    def __init__(
        self,
        *,
        users_response: dict[str, Any] | None = None,
        posts_response: dict[str, Any] | None = None,
    ):
        super().__init__(api_key="fake-token")
        self._users_response = users_response or {}
        self._posts_response = posts_response or {}

    @property
    def enabled(self) -> bool:
        return True

    async def __aenter__(self) -> _FakeTikHubClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def search_users(self, platform, query):  # type: ignore[override]
        return self._users_response

    async def user_posts(self, platform, username, *, sec_uid: str = "", count: int = 20):  # type: ignore[override]
        return self._posts_response


async def test_social_agent_filtra_posts_virales(indexed_db: AsyncIOMotorDatabase) -> None:
    """fetch_viral_posts solo devuelve los que pasan VIRAL_VIEWS_THRESHOLD."""
    fake = _FakeTikHubClient(
        posts_response={
            "data": [
                {
                    "aweme_id": "viral_1",
                    "desc": "Pulsar 200 #moto",
                    "statistics": {"play_count": 100_000, "digg_count": 5000},
                    "create_time": 1714000000,
                },
                {
                    "aweme_id": "low_1",
                    "desc": "common post",
                    "statistics": {"play_count": 10_000, "digg_count": 100},
                },
            ]
        }
    )
    agent = SocialAgent(fake)
    posts = await agent.fetch_viral_posts("rappi_motos", platform="tiktok")
    assert len(posts) == 1
    assert posts[0].post_external_id == "viral_1"


async def test_refresh_social_persiste_y_emite_evento_trending(
    indexed_db: AsyncIOMotorDatabase,
) -> None:
    """End-to-end: una watch_query activa · TikHub mockeado · upsert + evento."""
    await indexed_db[col.WATCH_QUERIES].insert_one(
        {
            "workspace_id": "RODDOS",
            "query": "repuestos TVS Raider 125",
            "source": "all",
            "activa": True,
            "prioridad": 1,
        }
    )

    fake = _FakeTikHubClient(
        users_response={
            "data": [
                {
                    "unique_id": "tvs_repuestos_co",
                    "follower_count": 80_000,
                    "total_favorited": 400_000,
                    "aweme_count": 150,
                    "signature": "Repuestos TVS Raider · Bogotá",
                    "share_url": "https://tiktok.com/@tvs_repuestos_co",
                    "sec_uid": "FAKE_SEC",
                }
            ]
        },
        posts_response={
            "data": [
                {
                    "aweme_id": "viral_post_1",
                    "desc": "Cadena para Raider · #raider",
                    "statistics": {"play_count": 200_000, "digg_count": 8000, "comment_count": 300},
                    "create_time": 1714000000,
                }
            ]
        },
    )
    agent = SocialAgent(fake)

    stats = await refresh_social(indexed_db, agent=agent)

    # Agent itera ig + tiktok · el mock devuelve el mismo user en ambas → 2 accounts
    # (una con plataforma=ig, otra con plataforma=tiktok · mismo username)
    assert stats.queries_processed == 1
    assert stats.accounts_created == 2
    # Posts: 2 detectados (uno por plataforma) pero el mismo post_external_id ·
    # dedup por post_external_id = 1 created
    assert stats.posts_detected == 2
    assert stats.posts_created == 1

    # Una doc por plataforma porque (workspace, plataforma, username) es unique
    accts = await indexed_db[col.SOCIAL_ACCOUNTS].find(
        {"username": "tvs_repuestos_co"}
    ).to_list(length=10)
    assert len(accts) == 2
    plataformas = {a["plataforma"] for a in accts}
    assert plataformas == {"ig", "tiktok"}
    assert all(a["seguidores"] == 80_000 for a in accts)

    # Post viral persistido (uno solo por dedup de post_external_id)
    posts = await indexed_db[col.SOCIAL_POSTS].find(
        {"post_external_id": "viral_post_1"}
    ).to_list(length=10)
    assert len(posts) == 1
    assert posts[0]["vistas"] == 200_000
    assert posts[0]["viral_flag"] is True

    # Eventos social.account.trending emitidos · uno por plataforma (ig + tiktok)
    events = await indexed_db[col.ARGOS_EVENTS].find(
        {"event_type": "social.account.trending", "payload.username": "tvs_repuestos_co"}
    ).to_list(length=10)
    assert len(events) == 2
    assert all(e["payload"]["seguidores"] == 80_000 for e in events)
    assert all(e["producer"] == "social_agent" for e in events)
