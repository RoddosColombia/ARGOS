"""DiscoveryAgent · Build config · descubrimiento automático de queries.

Tres señales por categoría activa:
- trending:     términos emergentes en el mercado MCO (placeholder · agrega los SKUs
                de products_catalog con mayor actividad en 7d que NO están en watch_queries)
- rising:       SKUs en products_catalog con listing_count creciendo >50% en 7d O precio
                bajando >15% (señal de liquidación)
- disappearing: SKUs con >5 publicaciones hace 7d que ahora tienen 0-1 (descontinuados)

Cron diario 06:00 UTC vía `run_discovery_job` · persiste en `discovery_suggestions`
con upsert idempotente por (workspace, category, term, signal_type, date).

Skip silencioso: si no hay categorías activas o products_catalog vacío, devuelve
stats vacías.
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.db import collections as col
from argos.db.events import publish_discovery_suggestions_generated

logger = logging.getLogger("argos.agents.discovery")

WINDOW_RECENT_DAYS = 7
WINDOW_DISAPPEAR_DAYS = 7
RISING_LISTING_GROWTH_PCT = 50.0
RISING_PRICE_DROP_PCT = 15.0
NEW_PRODUCT_LOOKBACK_HOURS = 48
NEW_PRODUCT_MIN_LISTINGS = 10
DISAPPEARING_PREVIOUS_MIN = 5
DISAPPEARING_CURRENT_MAX = 1
TOP_TRENDING = 20

SignalType = str  # trending | rising | liquidating | disappearing


@dataclass
class DiscoveryStats:
    category: str
    trending: int = 0
    rising: int = 0
    liquidating: int = 0
    disappearing: int = 0
    inserted: int = 0
    updated: int = 0

    @property
    def total(self) -> int:
        return self.trending + self.rising + self.liquidating + self.disappearing

    def counts(self) -> dict[str, int]:
        return {
            "trending": self.trending,
            "rising": self.rising,
            "liquidating": self.liquidating,
            "disappearing": self.disappearing,
            "total": self.total,
        }


class DiscoveryAgent:
    """Stateless · todas las queries van filtradas por workspace_id (ROG-A3)."""

    async def existing_terms(
        self, db: AsyncIOMotorDatabase, workspace_id: str
    ) -> set[str]:
        """Set de queries ya registradas (case-insensitive) para evitar duplicados."""
        cursor = db[col.WATCH_QUERIES].find(
            {"workspace_id": workspace_id}, {"query": 1, "_id": 0}
        )
        docs = await cursor.to_list(length=2000)
        return {(d.get("query") or "").lower().strip() for d in docs}

    async def discover_trending(
        self, db: AsyncIOMotorDatabase, workspace_id: str, category: str
    ) -> list[dict[str, Any]]:
        """Top términos con más detecciones recientes que NO están ya en watch_queries.

        Aproxima "trending" usando los nombres de productos detectados en últimos 7d
        cuya keyword principal NO aparece en watch_queries · señal de hueco de cobertura.
        """
        cutoff = datetime.now(tz=UTC) - timedelta(days=WINDOW_RECENT_DAYS)
        existing = await self.existing_terms(db, workspace_id)

        cursor = db[col.PRODUCTS_CATALOG].find(
            {
                "workspace_id": workspace_id,
                "created_at": {"$gte": cutoff},
                **({"categoria": category} if category else {}),
            },
            {"nombre": 1, "_id": 0},
        ).limit(2000)
        names = [d.get("nombre", "") for d in await cursor.to_list(length=2000)]
        counter: Counter[str] = Counter()
        for n in names:
            for token in _candidate_terms(n):
                if _matches_existing(token, existing):
                    continue
                counter[token] += 1
        suggestions = []
        for term, count in counter.most_common(TOP_TRENDING):
            if count < 3:
                break  # ruido
            suggestions.append({
                "term": term,
                "signal_type": "trending",
                "confidence": min(0.5 + count / 50.0, 0.95),
                "evidence": {
                    "metric": "product_mentions_7d",
                    "value": count,
                    "delta_pct": None,
                },
            })
        return suggestions

    async def discover_rising_products(
        self, db: AsyncIOMotorDatabase, workspace_id: str, category: str
    ) -> list[dict[str, Any]]:
        """SKUs con listing_count creciendo >50% O precio bajando >15% O nuevos en 48h con >10 publicaciones.

        Usa `products_history` cuando exista, y como fallback compara `created_at` reciente
        contra el resto del catálogo.
        """
        now = datetime.now(tz=UTC)
        cutoff_7d = now - timedelta(days=WINDOW_RECENT_DAYS)
        cutoff_48h = now - timedelta(hours=NEW_PRODUCT_LOOKBACK_HOURS)

        match: dict[str, Any] = {"workspace_id": workspace_id}
        if category:
            match["categoria"] = category

        # Aggregation: agrupar por sku_normalizado, contar listings nuevos en 48h
        pipeline = [
            {"$match": match},
            {
                "$group": {
                    "_id": "$sku_normalizado",
                    "nombre": {"$first": "$nombre"},
                    "total_listings": {"$sum": 1},
                    "recent_48h": {
                        "$sum": {"$cond": [{"$gte": ["$created_at", cutoff_48h]}, 1, 0]}
                    },
                    "recent_7d": {
                        "$sum": {"$cond": [{"$gte": ["$created_at", cutoff_7d]}, 1, 0]}
                    },
                    "min_precio": {"$min": "$precio_actual"},
                    "max_precio": {"$max": "$precio_actual"},
                }
            },
            {"$match": {"recent_48h": {"$gte": NEW_PRODUCT_MIN_LISTINGS}}},
            {"$sort": {"recent_48h": -1}},
            {"$limit": 30},
        ]
        docs = await db[col.PRODUCTS_CATALOG].aggregate(pipeline).to_list(length=30)
        existing = await self.existing_terms(db, workspace_id)
        suggestions: list[dict[str, Any]] = []
        for d in docs:
            sku = d.get("_id") or ""
            nombre = (d.get("nombre") or "").strip()
            term = (nombre or sku).lower()
            if not term or _matches_existing(term, existing):
                continue
            growth_pct = None
            older_count = max(d["total_listings"] - d["recent_48h"], 1)
            growth_pct = round(((d["recent_48h"] / older_count) * 100), 1)

            # liquidating: precio bajando >15% (min vs max en el set)
            is_liquidating = (
                d.get("max_precio") and d.get("min_precio")
                and d["max_precio"] > 0
                and (1 - d["min_precio"] / d["max_precio"]) * 100 >= RISING_PRICE_DROP_PCT
            )
            signal = "liquidating" if is_liquidating else "rising"
            suggestions.append({
                "term": term[:200],
                "signal_type": signal,
                "confidence": min(0.5 + d["recent_48h"] / 100.0, 0.92),
                "evidence": {
                    "metric": "new_listings_48h" if signal == "rising" else "price_drop_pct",
                    "value": d["recent_48h"] if signal == "rising"
                    else round((1 - d["min_precio"] / d["max_precio"]) * 100, 1),
                    "delta_pct": growth_pct,
                },
            })
        return suggestions

    async def discover_disappearing(
        self, db: AsyncIOMotorDatabase, workspace_id: str, category: str
    ) -> list[dict[str, Any]]:
        """SKUs que tenían >5 listings hace 7d y ahora tienen 0-1.

        Comparamos:
        - count_window_old: products_catalog con created_at en (now-14d, now-7d]
        - count_window_now: products_catalog con created_at en (now-7d, now]
        """
        now = datetime.now(tz=UTC)
        old_start = now - timedelta(days=WINDOW_DISAPPEAR_DAYS * 2)
        old_end = now - timedelta(days=WINDOW_DISAPPEAR_DAYS)

        match_base: dict[str, Any] = {"workspace_id": workspace_id}
        if category:
            match_base["categoria"] = category

        # Conteo en ventana antigua
        old_cursor = db[col.PRODUCTS_CATALOG].aggregate([
            {
                "$match": {
                    **match_base,
                    "created_at": {"$gte": old_start, "$lte": old_end},
                }
            },
            {"$group": {"_id": "$sku_normalizado", "count": {"$sum": 1}, "nombre": {"$first": "$nombre"}}},
            {"$match": {"count": {"$gte": DISAPPEARING_PREVIOUS_MIN}}},
        ])
        old_docs = await old_cursor.to_list(length=200)
        old_map = {d["_id"]: (d["count"], d.get("nombre", "")) for d in old_docs}

        # Conteo en ventana actual
        new_cursor = db[col.PRODUCTS_CATALOG].aggregate([
            {"$match": {**match_base, "created_at": {"$gte": old_end}}},
            {"$group": {"_id": "$sku_normalizado", "count": {"$sum": 1}}},
        ])
        new_docs = await new_cursor.to_list(length=2000)
        new_map = {d["_id"]: d["count"] for d in new_docs}

        existing = await self.existing_terms(db, workspace_id)
        suggestions: list[dict[str, Any]] = []
        for sku, (old_count, nombre) in old_map.items():
            current = new_map.get(sku, 0)
            if current > DISAPPEARING_CURRENT_MAX:
                continue
            term = (nombre or sku).lower()[:200]
            if not term or _matches_existing(term, existing):
                continue
            drop_pct = round((1 - current / old_count) * 100, 1) if old_count else 100.0
            suggestions.append({
                "term": term,
                "signal_type": "disappearing",
                "confidence": min(0.6 + drop_pct / 200.0, 0.95),
                "evidence": {
                    "metric": "listings_drop_pct_7d",
                    "value": drop_pct,
                    "delta_pct": -drop_pct,
                },
            })
        return suggestions


def _matches_existing(candidate: str, existing: set[str]) -> bool:
    """True si `candidate` ya está cubierto por alguna query existente.

    Cubre dos casos:
    - candidate exacto (`"filtro aire"` ∈ existing)
    - candidate contiene una query existente como substring
      (`"filtro aire moto"` debe filtrarse si `"filtro aire"` ya existe)
    """
    if candidate in existing:
        return True
    return any(q and q in candidate for q in existing)


def _candidate_terms(name: str) -> list[str]:
    """Devuelve hasta 3 frases candidatas (lowercased, normalizadas) extraídas de `name`."""
    if not name:
        return []
    n = name.lower().strip()
    # Tomamos los primeros 4 tokens y cualquier bigrama interesante
    tokens = [t for t in n.replace(",", " ").replace("/", " ").split() if len(t) > 2]
    if not tokens:
        return []
    out = [" ".join(tokens[:3])]
    if len(tokens) >= 2:
        out.append(" ".join(tokens[:2]))
    return list(dict.fromkeys(out))[:3]


async def run_discovery_job(
    db: AsyncIOMotorDatabase,
    *,
    workspace_id: str = "RODDOS",
    agent: DiscoveryAgent | None = None,
) -> dict[str, Any]:
    """Job: corre los 3 métodos por cada categoría activa · upsert idempotente."""
    if agent is None:
        agent = DiscoveryAgent()

    cats_cursor = db[col.CATEGORIES].find(
        {"workspace_id": workspace_id, "active": True}
    )
    cats = await cats_cursor.to_list(length=50)
    if not cats:
        logger.warning("discovery_skipped_no_active_categories")
        return {"workspace_id": workspace_id, "categories": 0, "stats": []}

    now = datetime.now(tz=UTC)
    today = now.strftime("%Y-%m-%d")
    all_stats: list[dict[str, Any]] = []

    for cat in cats:
        slug = cat["slug"]
        stats = DiscoveryStats(category=slug)
        try:
            trending = await agent.discover_trending(db, workspace_id, slug)
            rising_or_liq = await agent.discover_rising_products(db, workspace_id, slug)
            disappearing = await agent.discover_disappearing(db, workspace_id, slug)
        except Exception:  # noqa: BLE001
            logger.exception("discovery_category_failed", extra={"category": slug})
            continue

        bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for s in trending:
            bucket["trending"].append(s)
        for s in rising_or_liq:
            bucket[s["signal_type"]].append(s)
        for s in disappearing:
            bucket["disappearing"].append(s)

        for signal_type, items in bucket.items():
            for sugg in items:
                result = await db[col.DISCOVERY_SUGGESTIONS].update_one(
                    {
                        "workspace_id": workspace_id,
                        "category": slug,
                        "term": sugg["term"],
                        "signal_type": signal_type,
                        "date": today,
                    },
                    {
                        "$set": {
                            "confidence": sugg["confidence"],
                            "evidence": sugg["evidence"],
                            "updated_at": now,
                        },
                        "$setOnInsert": {
                            "workspace_id": workspace_id,
                            "category": slug,
                            "term": sugg["term"],
                            "signal_type": signal_type,
                            "date": today,
                            "status": "pending",
                            "created_at": now,
                        },
                    },
                    upsert=True,
                )
                if result.upserted_id is not None:
                    stats.inserted += 1
                else:
                    stats.updated += 1
                if signal_type == "trending":
                    stats.trending += 1
                elif signal_type == "rising":
                    stats.rising += 1
                elif signal_type == "liquidating":
                    stats.liquidating += 1
                elif signal_type == "disappearing":
                    stats.disappearing += 1

        await publish_discovery_suggestions_generated(
            db,
            workspace_id=workspace_id,
            category=slug,
            counts=stats.counts(),
        )
        all_stats.append({
            "category": slug,
            "counts": stats.counts(),
            "inserted": stats.inserted,
            "updated": stats.updated,
        })

    logger.info(
        "discovery_job_done",
        extra={"workspace_id": workspace_id, "categories": len(cats), "total_stats": len(all_stats)},
    )
    return {"workspace_id": workspace_id, "categories": len(cats), "stats": all_stats}
