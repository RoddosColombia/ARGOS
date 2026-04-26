"""Wrapper async sobre qdrant-client · Build 3.2 (GraphRAG / vector search).

Build 3.2: dos colecciones · `products_embeddings` y `ads_embeddings` ·
ambas con dim 1536 (matches OpenAI text-embedding-3-small) y métrica COSINE.

Skip silencioso si `QDRANT_URL` está vacío · `enabled=False` y todas las
operaciones devuelven valores neutros (lista vacía en search, no-op en upsert).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("argos.partners.qdrant")

PRODUCTS_COLLECTION = "products_embeddings"
ADS_COLLECTION = "ads_embeddings"
EMBEDDING_DIM = 1536  # OpenAI text-embedding-3-small


@dataclass
class QdrantHit:
    point_id: str
    score: float
    payload: dict[str, Any]


class QdrantBackend:
    """Cliente Qdrant async · skip silencioso sin URL."""

    def __init__(
        self,
        url: str = "",
        api_key: str = "",
    ) -> None:
        self._url = url
        self._api_key = api_key
        self._client: Any | None = None  # AsyncQdrantClient · lazy import

    @property
    def enabled(self) -> bool:
        return bool(self._url)

    async def _ensure_client(self) -> Any | None:
        if not self.enabled:
            return None
        if self._client is None:
            from qdrant_client import AsyncQdrantClient
            self._client = AsyncQdrantClient(url=self._url, api_key=self._api_key or None)
        return self._client

    async def ensure_collections(self) -> None:
        """Idempotente · crea las dos colecciones si no existen."""
        client = await self._ensure_client()
        if client is None:
            logger.warning("qdrant_skipped_no_url_ensure_collections")
            return
        from qdrant_client.models import Distance, VectorParams

        existing = await client.get_collections()
        existing_names = {c.name for c in existing.collections}
        for name in (PRODUCTS_COLLECTION, ADS_COLLECTION):
            if name not in existing_names:
                await client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
                )
                logger.info("qdrant_collection_created", extra={"collection": name})

    async def upsert_point(
        self,
        collection: str,
        *,
        point_id: str,
        vector: list[float],
        payload: dict[str, Any],
    ) -> bool:
        """Devuelve True si se persistió, False si no enabled."""
        client = await self._ensure_client()
        if client is None:
            return False
        from qdrant_client.models import PointStruct

        await client.upsert(
            collection_name=collection,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )
        return True

    async def search(
        self,
        collection: str,
        *,
        query_vector: list[float],
        limit: int = 10,
        workspace_id: str = "",
    ) -> list[QdrantHit]:
        """Búsqueda semántica · `[]` si no enabled."""
        client = await self._ensure_client()
        if client is None:
            return []
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        query_filter = None
        if workspace_id:
            query_filter = Filter(
                must=[FieldCondition(key="workspace_id", match=MatchValue(value=workspace_id))]
            )

        # qdrant-client >=1.10: usa query_points · fallback search en versiones viejas
        try:
            response = await client.query_points(
                collection_name=collection,
                query=query_vector,
                limit=limit,
                query_filter=query_filter,
                with_payload=True,
            )
            points = response.points
        except AttributeError:
            points = await client.search(
                collection_name=collection,
                query_vector=query_vector,
                limit=limit,
                query_filter=query_filter,
                with_payload=True,
            )

        return [
            QdrantHit(
                point_id=str(p.id),
                score=float(p.score or 0),
                payload=dict(p.payload or {}),
            )
            for p in points
        ]

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.close()
            except Exception:  # noqa: BLE001
                logger.exception("qdrant_close_failed")
            self._client = None
