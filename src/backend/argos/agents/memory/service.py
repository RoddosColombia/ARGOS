"""MemoryAgent · Build 3.2 · embeddings + vector search.

Pipeline:
- Job `memory_embed_job` cada 6h: query products_catalog + ads_library con
  `embedded_at=null` (o ausente), genera embedding con OpenAI
  text-embedding-3-small (1536 dim), upsert en Qdrant, marca `embedded_at=now`
  en MongoDB.
- Endpoint `GET /api/v1/memory/search?q=&type=&limit=` y método público
  `search_similar_products/ads` ejecutan búsqueda semántica.

Skip silencioso si `OPENAI_API_KEY` o `QDRANT_URL` faltan: jobs son no-op,
search devuelve [] con log warning · no levanta 500.

Voyage AI: env var `VOYAGE_API_KEY` reservada para futuro · Build 3.2 solo
usa OpenAI por consistencia de dimensión (1536 vs voyage-3 1024) · DT futura.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.config import get_settings
from argos.db import collections as col
from argos.partners.qdrant.client import (
    ADS_COLLECTION,
    PRODUCTS_COLLECTION,
    QdrantBackend,
    QdrantHit,
)

logger = logging.getLogger("argos.agents.memory")

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_PROVIDER = "openai"

DEFAULT_BATCH_SIZE = 50


@dataclass
class SearchHit:
    """Resultado normalizado para el endpoint y para el Strategist."""
    point_id: str
    score: float
    payload: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "point_id": self.point_id,
            "score": round(self.score, 4),
            **self.payload,
        }


class OpenAIEmbedder:
    """Genera embeddings · skip silencioso sin api_key."""

    def __init__(self, api_key: str = "", model: str = EMBEDDING_MODEL) -> None:
        self._api_key = api_key
        self._model = model
        self._client: Any | None = None

    @property
    def enabled(self) -> bool:
        return bool(self._api_key)

    async def _ensure_client(self) -> Any | None:
        if not self.enabled:
            return None
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Devuelve `[]` si no enabled · acepta lista (la API soporta batch)."""
        if not texts:
            return []
        client = await self._ensure_client()
        if client is None:
            return []
        response = await client.embeddings.create(model=self._model, input=texts)
        return [list(item.embedding) for item in response.data]

    async def embed_one(self, text: str) -> list[float] | None:
        results = await self.embed([text])
        return results[0] if results else None


def _build_product_text(doc: dict[str, Any]) -> str:
    parts: list[str] = []
    if nombre := doc.get("nombre"):
        parts.append(str(nombre))
    motos = doc.get("compatible_motos") or []
    if motos:
        parts.append("Compatible: " + ", ".join(str(m) for m in motos))
    if cat := doc.get("categoria"):
        parts.append(f"Categoría: {cat}")
    return " · ".join(parts).strip()


def _build_ad_text(doc: dict[str, Any]) -> str:
    parts: list[str] = []
    if anunciante := doc.get("anunciante"):
        parts.append(str(anunciante))
    if titulo := doc.get("copy_titulo"):
        parts.append(str(titulo))
    if texto := doc.get("copy_texto"):
        parts.append(str(texto)[:500])
    return " · ".join(parts).strip()


class MemoryAgent:
    """Coordina embeddings + Qdrant · usado por job + endpoint + Strategist."""

    def __init__(self, qdrant: QdrantBackend, embedder: OpenAIEmbedder) -> None:
        self._qdrant = qdrant
        self._embedder = embedder

    @property
    def enabled(self) -> bool:
        return self._qdrant.enabled and self._embedder.enabled

    async def embed_product(self, doc: dict[str, Any]) -> bool:
        """Embed + upsert en Qdrant. Devuelve True si persistió."""
        if not self.enabled:
            return False
        text = _build_product_text(doc)
        if not text:
            return False
        vector = await self._embedder.embed_one(text)
        if vector is None:
            return False
        return await self._qdrant.upsert_point(
            PRODUCTS_COLLECTION,
            point_id=str(doc["_id"]),
            vector=vector,
            payload={
                "workspace_id": doc.get("workspace_id", ""),
                "sku_normalizado": doc.get("sku_normalizado", ""),
                "nombre": doc.get("nombre", ""),
                "source": doc.get("source", ""),
                "precio_actual": float(doc.get("precio_actual") or 0),
                "compatible_motos": list(doc.get("compatible_motos") or []),
            },
        )

    async def embed_ad(self, doc: dict[str, Any]) -> bool:
        if not self.enabled:
            return False
        text = _build_ad_text(doc)
        if not text:
            return False
        vector = await self._embedder.embed_one(text)
        if vector is None:
            return False
        return await self._qdrant.upsert_point(
            ADS_COLLECTION,
            point_id=str(doc["_id"]),
            vector=vector,
            payload={
                "workspace_id": doc.get("workspace_id", ""),
                "plataforma": doc.get("plataforma", ""),
                "anunciante": doc.get("anunciante", ""),
                "copy_titulo": doc.get("copy_titulo", "")[:200],
                "ad_id_externo": doc.get("ad_id_externo", ""),
                "fuente_query": doc.get("fuente_query", ""),
            },
        )

    async def _search(
        self, collection: str, query_text: str, *, limit: int, workspace_id: str
    ) -> list[SearchHit]:
        if not self.enabled or not query_text.strip():
            if not self.enabled:
                logger.warning(
                    "memory_search_disabled",
                    extra={"qdrant_enabled": self._qdrant.enabled, "embedder_enabled": self._embedder.enabled},
                )
            return []
        vector = await self._embedder.embed_one(query_text)
        if vector is None:
            return []
        hits: list[QdrantHit] = await self._qdrant.search(
            collection, query_vector=vector, limit=limit, workspace_id=workspace_id
        )
        return [SearchHit(point_id=h.point_id, score=h.score, payload=h.payload) for h in hits]

    async def search_similar_products(
        self, query_text: str, *, limit: int = 10, workspace_id: str = "RODDOS"
    ) -> list[SearchHit]:
        return await self._search(PRODUCTS_COLLECTION, query_text, limit=limit, workspace_id=workspace_id)

    async def search_similar_ads(
        self, query_text: str, *, limit: int = 10, workspace_id: str = "RODDOS"
    ) -> list[SearchHit]:
        return await self._search(ADS_COLLECTION, query_text, limit=limit, workspace_id=workspace_id)


def _build_default_agent() -> MemoryAgent | None:
    settings = get_settings()
    qdrant = QdrantBackend(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    embedder = OpenAIEmbedder(api_key=settings.openai_api_key)
    if not (qdrant.enabled and embedder.enabled):
        logger.warning(
            "memory_agent_disabled",
            extra={"qdrant": qdrant.enabled, "openai": embedder.enabled},
        )
        return None
    return MemoryAgent(qdrant, embedder)


async def embed_pending_job(
    db: AsyncIOMotorDatabase,
    *,
    workspace_id: str = "RODDOS",
    agent: MemoryAgent | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict[str, int]:
    """Job: embed productos + ads con `embedded_at` null en mongo · marca embedded_at=now al persistir."""
    own_agent = False
    if agent is None:
        agent = _build_default_agent()
        own_agent = True
    if agent is None:
        return {"products_embedded": 0, "ads_embedded": 0, "skipped": 1}

    try:
        await agent._qdrant.ensure_collections()
    except Exception:  # noqa: BLE001
        logger.exception("memory_ensure_collections_failed")

    stats = {"products_embedded": 0, "ads_embedded": 0, "errors": 0}
    now = datetime.now(tz=UTC)

    # Productos pending
    pending_filter = {
        "workspace_id": workspace_id,
        "$or": [{"embedded_at": None}, {"embedded_at": {"$exists": False}}],
    }
    cursor = db[col.PRODUCTS_CATALOG].find(pending_filter).limit(batch_size)
    async for product in cursor:
        try:
            ok = await agent.embed_product(product)
            if ok:
                await db[col.PRODUCTS_CATALOG].update_one(
                    {"_id": product["_id"]}, {"$set": {"embedded_at": now}}
                )
                stats["products_embedded"] += 1
        except Exception:  # noqa: BLE001
            logger.exception("memory_embed_product_failed", extra={"product_id": str(product.get("_id"))})
            stats["errors"] += 1

    # Ads pending
    cursor = db[col.ADS_LIBRARY].find(pending_filter).limit(batch_size)
    async for ad in cursor:
        try:
            ok = await agent.embed_ad(ad)
            if ok:
                await db[col.ADS_LIBRARY].update_one(
                    {"_id": ad["_id"]}, {"$set": {"embedded_at": now}}
                )
                stats["ads_embedded"] += 1
        except Exception:  # noqa: BLE001
            logger.exception("memory_embed_ad_failed", extra={"ad_id": str(ad.get("_id"))})
            stats["errors"] += 1

    if own_agent:
        await agent._qdrant.close()

    logger.info("memory_embed_job_done", extra=stats)
    return stats
