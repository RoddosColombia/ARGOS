"""Cliente async para TikHub.io · Build 2.3 (social listening IG/TikTok).

Docs: https://docs.tikhub.io/

Auth: header `Authorization: Bearer {api_key}`. Sin key → skip silencioso.
La API expone 900+ endpoints con shapes muy distintas; este cliente abstrae
solo los que el SocialAgent necesita y deja la normalización al agent.

Endpoints Build 2.3 (TikTok web scraping endpoints estables):
- `/api/v1/tiktok/web/fetch_user_search_result?keyword=KEY` → users TikTok
- `/api/v1/instagram/web/fetch_search_user?keyword=KEY` → users IG
- `/api/v1/tiktok/web/fetch_user_post?secUid=XXX&count=N` → posts TikTok
- `/api/v1/instagram/web/fetch_user_posts?username=XXX` → posts IG
"""
from __future__ import annotations

import logging
from typing import Any, Literal

import httpx

logger = logging.getLogger("argos.partners.tikhub")

TIKHUB_BASE_URL = "https://api.tikhub.io"
DEFAULT_TIMEOUT_SECONDS = 30.0

Platform = Literal["tiktok", "ig"]


class TikHubError(Exception):
    def __init__(self, status: int, message: str) -> None:
        self.status = status
        self.message = message
        super().__init__(f"TikHub {status}: {message}")


class TikHubClient:
    """Async context manager · skip silencioso sin api_key."""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = TIKHUB_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def enabled(self) -> bool:
        return bool(self._api_key)

    async def __aenter__(self) -> TikHubClient:
        if self.enabled:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.enabled or self._client is None:
            logger.warning("tikhub_skipped_no_key", extra={"path": path})
            return {}
        try:
            resp = await self._client.get(path, params=params or {})
        except httpx.HTTPError as exc:
            logger.warning("tikhub_http_error", extra={"path": path, "error": str(exc)[:200]})
            raise TikHubError(0, f"http_error: {type(exc).__name__}") from exc

        if resp.status_code == 401:
            raise TikHubError(401, "TikHub key inválida")
        if resp.status_code == 429:
            raise TikHubError(429, "TikHub rate limited")
        if resp.status_code >= 400:
            raise TikHubError(resp.status_code, resp.text[:200])

        data = resp.json()
        if not isinstance(data, dict):
            return {}
        return data

    async def search_users(self, platform: Platform, query: str) -> dict[str, Any]:
        """Devuelve el JSON crudo del response · `{}` si no enabled."""
        if platform == "tiktok":
            return await self._get(
                "/api/v1/tiktok/web/fetch_user_search_result",
                params={"keyword": query},
            )
        return await self._get(
            "/api/v1/instagram/web/fetch_search_user",
            params={"keyword": query},
        )

    async def user_posts(
        self,
        platform: Platform,
        username: str,
        *,
        sec_uid: str = "",
        count: int = 20,
    ) -> dict[str, Any]:
        """Posts del usuario · TikTok requiere sec_uid (el user search lo expone)."""
        if platform == "tiktok":
            params: dict[str, Any] = {"count": count}
            if sec_uid:
                params["secUid"] = sec_uid
            else:
                params["unique_id"] = username
            return await self._get("/api/v1/tiktok/web/fetch_user_post", params=params)
        return await self._get(
            "/api/v1/instagram/web/fetch_user_posts",
            params={"username": username},
        )
