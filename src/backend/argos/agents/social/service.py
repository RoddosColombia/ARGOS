"""Social Agent · Build 2.3 (TikHub.io · IG + TikTok).

Pipeline:
- Itera watch_queries activas con source="all"
- Por cada keyword + plataforma (ig, tiktok) busca cuentas relevantes
- Persiste en `social_accounts` con upsert idempotente
- Para top N cuentas trae sus posts virales (≥ 50K vistas) → `social_posts`
- Emite `social.account.trending` cuando entra una cuenta nueva al catálogo
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.agents.scout.queries_repo import get_active_queries
from argos.config import get_settings
from argos.db import collections as col
from argos.db.events import publish_social_account_trending
from argos.partners.tikhub.client import Platform, TikHubClient, TikHubError

logger = logging.getLogger("argos.agents.social")

VIRAL_VIEWS_THRESHOLD = 50_000
DEFAULT_TOP_ACCOUNTS_PER_QUERY = 5
DEFAULT_POSTS_PER_ACCOUNT = 10
PLATFORMS: tuple[Platform, ...] = ("ig", "tiktok")


@dataclass
class SocialAccount:
    plataforma: Platform
    username: str
    seguidores: int
    engagement_rate: float
    descripcion: str
    url_perfil: str
    relevancia_score: float
    sec_uid: str = ""  # solo TikTok · necesario para fetch posts


@dataclass
class SocialPost:
    plataforma: Platform
    username: str
    post_external_id: str
    url_post: str
    descripcion: str
    vistas: int
    likes: int
    comentarios: int
    hashtags: list[str]
    fecha_publicacion: datetime | None


@dataclass
class SocialRefreshStats:
    queries_processed: int = 0
    accounts_detected: int = 0
    accounts_created: int = 0
    posts_detected: int = 0
    posts_created: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "queries_processed": self.queries_processed,
            "accounts_detected": self.accounts_detected,
            "accounts_created": self.accounts_created,
            "posts_detected": self.posts_detected,
            "posts_created": self.posts_created,
            "errors": list(self.errors),
        }


def _parse_date(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
    if isinstance(raw, (int, float)):
        try:
            ts = float(raw)
            if ts > 10_000_000_000:
                ts /= 1000
            return datetime.fromtimestamp(ts, tz=UTC)
        except (ValueError, OSError):
            return None
    if isinstance(raw, str):
        s = raw.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except ValueError:
            return None
    return None


def _extract_hashtags(text: str) -> list[str]:
    if not text:
        return []
    return list({tag.lower() for tag in [w.lstrip("#") for w in text.split() if w.startswith("#")] if tag})


def parse_tikhub_account(raw: dict[str, Any], platform: Platform) -> SocialAccount | None:
    """Normaliza un user item de TikHub a SocialAccount · None si inválido.

    Soporta variantes de field names entre tiktok y ig + entre versiones del API.
    """
    username = (
        raw.get("unique_id")
        or raw.get("username")
        or raw.get("nickname")
        or raw.get("user_name")
        or ""
    )
    if not username:
        return None

    seguidores = (
        raw.get("follower_count")
        or raw.get("followers_count")
        or raw.get("followers")
        or 0
    )
    likes_total = raw.get("total_favorited") or raw.get("heart_count") or 0
    posts_count = raw.get("aweme_count") or raw.get("media_count") or raw.get("post_count") or 0

    # Engagement rate heuristic: avg likes per post / followers · cap a 100%
    avg_likes = likes_total / posts_count if posts_count > 0 else 0
    engagement = (avg_likes / seguidores * 100) if seguidores > 0 else 0.0
    engagement = min(round(engagement, 2), 100.0)

    # Relevance score · seguidores log scale + engagement rate · normalizado 0-100
    import math
    follower_score = math.log10(max(seguidores, 1)) * 10  # log scale 1k=30, 10k=40, 100k=50, 1M=60
    relevancia = min(round(follower_score + engagement * 2, 2), 100.0)

    return SocialAccount(
        plataforma=platform,
        username=str(username)[:200],
        seguidores=int(seguidores),
        engagement_rate=engagement,
        descripcion=str(raw.get("signature") or raw.get("biography") or "")[:500],
        url_perfil=str(raw.get("share_url") or raw.get("profile_url") or "")[:500],
        relevancia_score=relevancia,
        sec_uid=str(raw.get("sec_uid") or raw.get("secUid") or ""),
    )


def parse_tikhub_post(raw: dict[str, Any], platform: Platform, username: str) -> SocialPost | None:
    """Normaliza un post item de TikHub a SocialPost · None si inválido."""
    post_id = (
        raw.get("aweme_id")
        or raw.get("id")
        or raw.get("media_id")
        or raw.get("pk")
    )
    if not post_id:
        return None

    statistics = raw.get("statistics") or raw
    vistas = (
        statistics.get("play_count")
        or statistics.get("video_view_count")
        or raw.get("play_count")
        or raw.get("view_count")
        or 0
    )
    likes = (
        statistics.get("digg_count")
        or statistics.get("like_count")
        or raw.get("digg_count")
        or raw.get("like_count")
        or 0
    )
    comentarios = (
        statistics.get("comment_count")
        or raw.get("comment_count")
        or 0
    )

    descripcion = str(raw.get("desc") or raw.get("caption") or raw.get("title") or "")[:1000]
    hashtags = _extract_hashtags(descripcion)
    fecha = _parse_date(
        raw.get("create_time") or raw.get("created_at") or raw.get("taken_at")
    )
    url_post = str(
        raw.get("share_url")
        or raw.get("permalink")
        or raw.get("post_url")
        or ""
    )[:500]

    return SocialPost(
        plataforma=platform,
        username=username[:200],
        post_external_id=str(post_id),
        url_post=url_post,
        descripcion=descripcion,
        vistas=int(vistas),
        likes=int(likes),
        comentarios=int(comentarios),
        hashtags=hashtags[:30],
        fecha_publicacion=fecha,
    )


def _extract_users(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Tolera múltiples shapes de respuesta TikHub para search users."""
    if not isinstance(raw, dict):
        return []
    for key in ("data", "users", "user_list", "results"):
        candidate = raw.get(key)
        if isinstance(candidate, list) and candidate:
            return [c for c in candidate if isinstance(c, dict)]
        # Algunas respuestas vienen anidadas data.users
        if isinstance(candidate, dict):
            for nested in ("users", "user_list", "results", "items"):
                inner = candidate.get(nested)
                if isinstance(inner, list) and inner:
                    return [c for c in inner if isinstance(c, dict)]
    return []


def _extract_posts(raw: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(raw, dict):
        return []
    for key in ("data", "aweme_list", "posts", "items", "media"):
        candidate = raw.get(key)
        if isinstance(candidate, list) and candidate:
            return [c for c in candidate if isinstance(c, dict)]
        if isinstance(candidate, dict):
            for nested in ("aweme_list", "posts", "items", "media"):
                inner = candidate.get(nested)
                if isinstance(inner, list) and inner:
                    return [c for c in inner if isinstance(c, dict)]
    return []


class SocialAgent:
    """Wrapper sobre TikHubClient + métodos públicos para Scout/job."""

    def __init__(self, client: TikHubClient) -> None:
        self._client = client

    async def fetch_trending_accounts(
        self, query: str, *, platforms: tuple[Platform, ...] = PLATFORMS
    ) -> list[SocialAccount]:
        """Busca cuentas en cada plataforma · errores aislados por plataforma."""
        results: list[SocialAccount] = []
        for plat in platforms:
            try:
                raw = await self._client.search_users(plat, query)
                for user_raw in _extract_users(raw):
                    parsed = parse_tikhub_account(user_raw, plat)
                    if parsed is not None:
                        results.append(parsed)
            except TikHubError as exc:
                logger.warning(
                    "social_search_users_error",
                    extra={"query": query, "platform": plat, "status": exc.status},
                )
        return results

    async def fetch_viral_posts(
        self, username: str, platform: Platform, *, sec_uid: str = ""
    ) -> list[SocialPost]:
        """Trae posts del user · filtra los virales (>= VIRAL_VIEWS_THRESHOLD)."""
        try:
            raw = await self._client.user_posts(platform, username, sec_uid=sec_uid)
        except TikHubError as exc:
            logger.warning(
                "social_user_posts_error",
                extra={"username": username, "platform": platform, "status": exc.status},
            )
            return []

        viral: list[SocialPost] = []
        for post_raw in _extract_posts(raw):
            parsed = parse_tikhub_post(post_raw, platform, username)
            if parsed is None:
                continue
            if parsed.vistas >= VIRAL_VIEWS_THRESHOLD:
                viral.append(parsed)
        return viral


async def _upsert_account(
    db: AsyncIOMotorDatabase,
    account: SocialAccount,
    *,
    workspace_id: str,
    fuente_query: str,
) -> bool:
    """Upsert · devuelve True si fue creada (no existía)."""
    now = datetime.now(tz=UTC)
    set_fields = {
        "workspace_id": workspace_id,
        "plataforma": account.plataforma,
        "username": account.username,
        "seguidores": account.seguidores,
        "engagement_rate": account.engagement_rate,
        "descripcion": account.descripcion,
        "url_perfil": account.url_perfil,
        "relevancia_score": account.relevancia_score,
        "sec_uid": account.sec_uid,
        "fuente_query": fuente_query,
        "ultima_metricas_at": now,
        "updated_at": now,
    }
    set_on_insert = {"created_at": now}

    result = await db[col.SOCIAL_ACCOUNTS].update_one(
        {
            "workspace_id": workspace_id,
            "plataforma": account.plataforma,
            "username": account.username,
        },
        {"$set": set_fields, "$setOnInsert": set_on_insert},
        upsert=True,
    )
    return result.upserted_id is not None


async def _upsert_post(
    db: AsyncIOMotorDatabase,
    post: SocialPost,
    *,
    workspace_id: str,
) -> bool:
    """Upsert post · devuelve True si fue creado."""
    now = datetime.now(tz=UTC)
    set_fields = {
        "workspace_id": workspace_id,
        "plataforma": post.plataforma,
        "username": post.username,
        "post_external_id": post.post_external_id,
        "url_post": post.url_post,
        "descripcion": post.descripcion,
        "vistas": post.vistas,
        "likes": post.likes,
        "comentarios": post.comentarios,
        "hashtags": post.hashtags,
        "fecha_publicacion": post.fecha_publicacion,
        "viral_flag": True,  # solo guardamos los que pasaron el threshold
        "updated_at": now,
    }
    set_on_insert = {"created_at": now}

    result = await db[col.SOCIAL_POSTS].update_one(
        {"workspace_id": workspace_id, "post_external_id": post.post_external_id},
        {"$set": set_fields, "$setOnInsert": set_on_insert},
        upsert=True,
    )
    return result.upserted_id is not None


async def refresh_social(
    db: AsyncIOMotorDatabase,
    *,
    workspace_id: str = "RODDOS",
    agent: SocialAgent | None = None,
    queries_override: list[dict[str, Any]] | None = None,
    top_accounts_per_query: int = DEFAULT_TOP_ACCOUNTS_PER_QUERY,
) -> SocialRefreshStats:
    """Job: itera watch_queries activas con source=all · busca cuentas + posts virales."""
    stats = SocialRefreshStats()
    settings = get_settings()

    queries = queries_override
    if queries is None:
        queries = await get_active_queries(db, workspace_id)
    queries = [q for q in queries if q.get("source") in ("all", "tiktok", "ig")]
    if not queries:
        logger.warning("social_no_active_queries", extra={"workspace_id": workspace_id})
        return stats

    own_agent = agent is None
    own_client: TikHubClient | None = None
    if own_agent:
        own_client = TikHubClient(api_key=settings.tikhub_api_key)
        await own_client.__aenter__()
        if not own_client.enabled:
            logger.info("social_skipped_no_tikhub_key")
            await own_client.__aexit__(None, None, None)
            return stats
        agent = SocialAgent(own_client)

    try:
        for q in queries:
            query_str = q["query"]
            try:
                accounts = await agent.fetch_trending_accounts(query_str)
                # Top N por relevancia_score
                top_accounts = sorted(
                    accounts, key=lambda a: a.relevancia_score, reverse=True
                )[:top_accounts_per_query]

                for account in top_accounts:
                    created = await _upsert_account(
                        db, account, workspace_id=workspace_id, fuente_query=query_str
                    )
                    stats.accounts_detected += 1
                    if created:
                        stats.accounts_created += 1
                        await publish_social_account_trending(
                            db,
                            workspace_id=workspace_id,
                            plataforma=account.plataforma,
                            username=account.username,
                            seguidores=account.seguidores,
                            relevancia_score=account.relevancia_score,
                            fuente_query=query_str,
                        )

                    # Posts virales de la cuenta
                    viral = await agent.fetch_viral_posts(
                        account.username, account.plataforma, sec_uid=account.sec_uid
                    )
                    for post in viral:
                        post_created = await _upsert_post(
                            db, post, workspace_id=workspace_id
                        )
                        stats.posts_detected += 1
                        if post_created:
                            stats.posts_created += 1

                stats.queries_processed += 1
            except Exception as exc:  # noqa: BLE001
                logger.exception("social_query_failed", extra={"query": query_str})
                stats.errors.append(
                    {"query": query_str, "error": f"{type(exc).__name__}: {str(exc)[:180]}"}
                )
    finally:
        if own_client is not None:
            await own_client.__aexit__(None, None, None)

    logger.info("social_refresh_done", extra=stats.as_dict())
    return stats
