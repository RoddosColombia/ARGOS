"""Competitors Agent · Meta Ad Library scraping vía Apify (Build 2.1).

Itera watch_queries activas, llama al actor `apify~facebook-ad-library-scraper`
por cada keyword, normaliza items a schema `ads_library` y emite
`competitors.ad.detected`.

Schema de output del actor (puede variar versión a versión · parser tolerante):
- ad_archive_id / id (str) · ad_id_externo
- page_name / advertiser (str) · anunciante
- ad_creative_body / body (str) · copy_texto
- ad_creative_link_title / title (str) · copy_titulo
- ad_creative_link_url / link_url (str) · url_landing
- ad_delivery_start_time / start_date (date)
- ad_delivery_stop_time (None si activo)
- creative_type / format (str) · formato (image/video/carousel)
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
from argos.db.events import publish_competitors_ad_detected
from argos.partners.apify.client import ApifyClient, ApifyError

logger = logging.getLogger("argos.agents.competitors")

DEFAULT_RESULTS_PER_QUERY = 30


@dataclass
class MetaAdsRefreshStats:
    queries_processed: int = 0
    ads_detected: int = 0
    ads_created: int = 0
    ads_updated: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "queries_processed": self.queries_processed,
            "ads_detected": self.ads_detected,
            "ads_created": self.ads_created,
            "ads_updated": self.ads_updated,
            "errors": list(self.errors),
        }


def _parse_date(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
    if isinstance(raw, str):
        # Apify suele devolver "2026-04-01T00:00:00.000Z" o "2026-04-01"
        s = raw.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except ValueError:
            return None
    if isinstance(raw, (int, float)):
        # epoch seconds o ms · heurística por magnitud
        try:
            ts = float(raw)
            if ts > 10_000_000_000:  # ms
                ts /= 1000
            return datetime.fromtimestamp(ts, tz=UTC)
        except (ValueError, OSError):
            return None
    return None


def _detect_formato(raw: dict[str, Any]) -> str:
    fmt_raw = (
        raw.get("creative_type")
        or raw.get("format")
        or raw.get("ad_creative_type")
        or ""
    )
    s = str(fmt_raw).lower()
    if "video" in s:
        return "video"
    if "carousel" in s or "carrusel" in s:
        return "carousel"
    if "image" in s or "photo" in s:
        return "image"
    if raw.get("video_url") or raw.get("video"):
        return "video"
    return "unknown"


def parse_apify_ad_item(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Normaliza un ad de Apify FB Ad Library al schema interno · None si inválido."""
    ad_id = raw.get("ad_archive_id") or raw.get("id") or raw.get("ad_id")
    if not ad_id:
        return None
    page_name = raw.get("page_name") or raw.get("advertiser") or raw.get("page") or ""
    if not page_name:
        return None

    fecha_inicio = _parse_date(raw.get("ad_delivery_start_time") or raw.get("start_date"))
    fecha_fin = _parse_date(raw.get("ad_delivery_stop_time") or raw.get("end_date"))
    activo = fecha_fin is None

    if fecha_inicio is None:
        return None

    end_for_calc = fecha_fin if fecha_fin else datetime.now(tz=UTC)
    durabilidad = max(0, (end_for_calc - fecha_inicio).days)

    return {
        "ad_id_externo": str(ad_id),
        "anunciante": str(page_name)[:200],
        "copy_texto": str(raw.get("ad_creative_body") or raw.get("body") or "")[:2000],
        "copy_titulo": str(
            raw.get("ad_creative_link_title")
            or raw.get("title")
            or ""
        )[:300],
        "url_landing": str(
            raw.get("ad_creative_link_url")
            or raw.get("link_url")
            or raw.get("snapshot_url")
            or ""
        )[:500],
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "durabilidad_dias": int(durabilidad),
        "formato": _detect_formato(raw),
        "activo": activo,
    }


async def upsert_meta_ad(
    db: AsyncIOMotorDatabase,
    apify_item: dict[str, Any],
    *,
    workspace_id: str,
    fuente_query: str,
    emit_events: bool = True,
) -> tuple[bool, str | None]:
    """Upsert de un ad Apify a `ads_library` · devuelve (created, ad_id_externo).

    Si `parse_apify_ad_item` retorna None → (False, None) sin tocar DB.
    """
    parsed = parse_apify_ad_item(apify_item)
    if parsed is None:
        logger.warning("ad_item_invalid", extra={"raw_keys": list(apify_item.keys())})
        return False, None

    now = datetime.now(tz=UTC)
    set_fields = {
        "workspace_id": workspace_id,
        "plataforma": "meta",
        "anunciante": parsed["anunciante"],
        "copy_texto": parsed["copy_texto"],
        "copy_titulo": parsed["copy_titulo"],
        "url_landing": parsed["url_landing"],
        "fecha_inicio": parsed["fecha_inicio"],
        "fecha_fin": parsed["fecha_fin"],
        "durabilidad_dias": parsed["durabilidad_dias"],
        "formato": parsed["formato"],
        "activo": parsed["activo"],
        "fuente_query": fuente_query,
        "ultima_deteccion": now,
        "updated_at": now,
    }
    set_on_insert = {
        "ad_id_externo": parsed["ad_id_externo"],
        "primera_deteccion": now,
        "created_at": now,
    }

    result = await db[col.ADS_LIBRARY].update_one(
        {
            "workspace_id": workspace_id,
            "plataforma": "meta",
            "ad_id_externo": parsed["ad_id_externo"],
        },
        {"$set": set_fields, "$setOnInsert": set_on_insert},
        upsert=True,
    )
    created = result.upserted_id is not None

    if emit_events and created:
        # Solo emitimos cuando es ad nuevo · re-detecciones del mismo ad solo
        # actualizan ultima_deteccion sin spamear el bus.
        await publish_competitors_ad_detected(
            db,
            workspace_id=workspace_id,
            plataforma="meta",
            ad_id_externo=parsed["ad_id_externo"],
            anunciante=parsed["anunciante"],
            copy_titulo=parsed["copy_titulo"],
            fuente_query=fuente_query,
            durabilidad_dias=parsed["durabilidad_dias"],
            formato=parsed["formato"],
        )

    return created, parsed["ad_id_externo"]


async def refresh_meta_ads(
    db: AsyncIOMotorDatabase,
    *,
    workspace_id: str = "RODDOS",
    apify_client: ApifyClient | None = None,
    queries_override: list[dict[str, Any]] | None = None,
    results_per_query: int = DEFAULT_RESULTS_PER_QUERY,
) -> MetaAdsRefreshStats:
    """Job: itera watch_queries activas, scrapa Meta Ad Library, upsert ads."""
    stats = MetaAdsRefreshStats()
    settings = get_settings()

    queries = queries_override
    if queries is None:
        queries = await get_active_queries(db, workspace_id)
    if not queries:
        logger.warning("competitors_no_active_queries", extra={"workspace_id": workspace_id})
        return stats

    own_apify = apify_client is None
    if own_apify:
        apify_client = ApifyClient(api_token=settings.apify_api_token)
        await apify_client.__aenter__()

    if not apify_client.enabled:
        logger.info("competitors_meta_ads_skipped_no_apify_token")
        if own_apify:
            await apify_client.__aexit__(None, None, None)
        return stats

    try:
        for q in queries:
            query_str = q["query"]
            try:
                items = await apify_client.fb_ad_library_search(
                    query_str, max_items=results_per_query
                )
                for raw in items:
                    created, _ = await upsert_meta_ad(
                        db, raw, workspace_id=workspace_id, fuente_query=query_str
                    )
                    stats.ads_detected += 1
                    if created:
                        stats.ads_created += 1
                    else:
                        stats.ads_updated += 1
                stats.queries_processed += 1
            except ApifyError as exc:
                logger.warning(
                    "competitors_apify_error",
                    extra={"query": query_str, "status": exc.status},
                )
                stats.errors.append({"query": query_str, "error": f"apify_{exc.status}"})
            except Exception as exc:  # noqa: BLE001
                logger.exception("competitors_query_failed", extra={"query": query_str})
                stats.errors.append(
                    {"query": query_str, "error": f"{type(exc).__name__}: {str(exc)[:180]}"}
                )
    finally:
        if own_apify:
            await apify_client.__aexit__(None, None, None)

    logger.info("meta_ads_refresh_done", extra=stats.as_dict())
    return stats
