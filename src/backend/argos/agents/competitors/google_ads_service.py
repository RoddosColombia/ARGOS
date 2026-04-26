"""Competitors Agent · subcomponente Google Ads Transparency (Build 2.2).

Itera watch_queries activas, consulta SerpAPI Google Ads Transparency Center
por cada keyword, normaliza al schema `ads_library` con plataforma="google" y
emite `competitors.ad.detected` (mismo evento que Meta · diferenciado por
`payload.plataforma`).

Build 2.2: campo adicional `keywords_pautadas: list[str]`. La transparency
center API no expone targeting real · poblar con `[fuente_query]` por ahora.
DT futura cuando aparezca un endpoint o scraping con esa info.
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
from argos.partners.serpapi.client import SerpApiClient, SerpApiError
from argos.partners.serpapi.google_ads import search_google_ads_transparency

logger = logging.getLogger("argos.agents.competitors.google")

DEFAULT_RESULTS_PER_QUERY = 30


@dataclass
class GoogleAdsRefreshStats:
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
    """Soporta ISO 8601 con/sin Z, ISO sin tz, epoch s/ms, datetime, o None."""
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
    if isinstance(raw, str):
        s = raw.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except ValueError:
            # Algunos ads transparency vienen con "2026-04-01" sin time
            try:
                dt = datetime.strptime(s, "%Y-%m-%d")
                return dt.replace(tzinfo=UTC)
            except ValueError:
                return None
    if isinstance(raw, (int, float)):
        try:
            ts = float(raw)
            if ts > 10_000_000_000:
                ts /= 1000
            return datetime.fromtimestamp(ts, tz=UTC)
        except (ValueError, OSError):
            return None
    return None


def _detect_formato_google(raw: dict[str, Any]) -> str:
    """SerpAPI google_ads_transparency suele devolver `format` en MAYÚSCULAS."""
    fmt = (
        raw.get("format")
        or raw.get("creative_format")
        or raw.get("ad_format")
        or ""
    )
    s = str(fmt).lower()
    if "video" in s:
        return "video"
    if "image" in s or "display" in s:
        return "image"
    if "responsive" in s or "html" in s:
        return "image"  # responsive search ads se renderizan visualmente como imagen + texto
    if "text" in s:
        return "text"
    return "unknown"


def parse_serpapi_google_ad(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Normaliza un ad de Google Ads Transparency a schema ads_library · None si inválido."""
    creative_id = (
        raw.get("creative_id")
        or raw.get("ad_id")
        or raw.get("id")
    )
    if not creative_id:
        return None
    advertiser = (
        raw.get("advertiser_name")
        or raw.get("advertiser")
        or raw.get("page_name")
        or ""
    )
    if not advertiser:
        return None

    fecha_inicio = _parse_date(
        raw.get("first_shown")
        or raw.get("first_shown_date")
        or raw.get("start_date")
    )
    fecha_fin = _parse_date(
        raw.get("last_shown")
        or raw.get("last_shown_date")
        or raw.get("end_date")
    )

    if fecha_inicio is None:
        return None

    # Si last_shown es muy reciente (< 7 días), probablemente sigue activo
    now = datetime.now(tz=UTC)
    activo = fecha_fin is None or (now - fecha_fin).days < 7

    end_for_calc = fecha_fin if fecha_fin else now
    durabilidad = max(0, (end_for_calc - fecha_inicio).days)

    copy_texto = str(
        raw.get("creative_text")
        or raw.get("description")
        or raw.get("body")
        or ""
    )[:2000]
    copy_titulo = str(
        raw.get("headline")
        or raw.get("title")
        or raw.get("creative_title")
        or ""
    )[:300]
    url_landing = str(
        raw.get("destination_url")
        or raw.get("landing_url")
        or raw.get("url")
        or ""
    )[:500]

    return {
        "ad_id_externo": str(creative_id),
        "anunciante": str(advertiser)[:200],
        "copy_texto": copy_texto,
        "copy_titulo": copy_titulo,
        "url_landing": url_landing,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "durabilidad_dias": int(durabilidad),
        "formato": _detect_formato_google(raw),
        "activo": activo,
    }


async def upsert_google_ad(
    db: AsyncIOMotorDatabase,
    serpapi_item: dict[str, Any],
    *,
    workspace_id: str,
    fuente_query: str,
    emit_events: bool = True,
) -> tuple[bool, str | None]:
    """Upsert de un ad Google a `ads_library` · devuelve (created, ad_id_externo)."""
    parsed = parse_serpapi_google_ad(serpapi_item)
    if parsed is None:
        logger.warning("google_ad_invalid", extra={"raw_keys": list(serpapi_item.keys())})
        return False, None

    now = datetime.now(tz=UTC)
    set_fields = {
        "workspace_id": workspace_id,
        "plataforma": "google",
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

    # NOTA: `$addToSet` y `$setOnInsert` no pueden tocar el mismo path en una
    # update (Mongo error 40 · path conflict). `$addToSet` se encarga solo:
    # crea el array en insert si no existe + acumula queries únicas en
    # re-detection (semántica set, no append-duplicates).
    result = await db[col.ADS_LIBRARY].update_one(
        {
            "workspace_id": workspace_id,
            "plataforma": "google",
            "ad_id_externo": parsed["ad_id_externo"],
        },
        {
            "$set": set_fields,
            "$setOnInsert": set_on_insert,
            "$addToSet": {"keywords_pautadas": fuente_query},
        },
        upsert=True,
    )
    created = result.upserted_id is not None

    if emit_events and created:
        await publish_competitors_ad_detected(
            db,
            workspace_id=workspace_id,
            plataforma="google",
            ad_id_externo=parsed["ad_id_externo"],
            anunciante=parsed["anunciante"],
            copy_titulo=parsed["copy_titulo"],
            fuente_query=fuente_query,
            durabilidad_dias=parsed["durabilidad_dias"],
            formato=parsed["formato"],
        )

    return created, parsed["ad_id_externo"]


async def refresh_google_ads(
    db: AsyncIOMotorDatabase,
    *,
    workspace_id: str = "RODDOS",
    serpapi_client: SerpApiClient | None = None,
    queries_override: list[dict[str, Any]] | None = None,
    results_per_query: int = DEFAULT_RESULTS_PER_QUERY,  # noqa: ARG001 — reservado para Build 2.3
) -> GoogleAdsRefreshStats:
    """Job: itera watch_queries activas, consulta Google Ads Transparency, upsert ads.

    Skip silencioso sin SERPAPI_API_KEY · errores aislados por keyword.
    """
    stats = GoogleAdsRefreshStats()
    settings = get_settings()

    queries = queries_override
    if queries is None:
        queries = await get_active_queries(db, workspace_id)
    if not queries:
        logger.warning("competitors_google_no_active_queries", extra={"workspace_id": workspace_id})
        return stats

    own_client = serpapi_client is None
    if own_client:
        serpapi_client = SerpApiClient(api_key=settings.serpapi_api_key)
        await serpapi_client.__aenter__()

    if not serpapi_client.enabled:
        logger.info("competitors_google_skipped_no_serpapi_key")
        if own_client:
            await serpapi_client.__aexit__(None, None, None)
        return stats

    try:
        for q in queries:
            query_str = q["query"]
            try:
                items = await search_google_ads_transparency(
                    query_str, client=serpapi_client
                )
                for raw in items:
                    created, _ = await upsert_google_ad(
                        db, raw, workspace_id=workspace_id, fuente_query=query_str
                    )
                    stats.ads_detected += 1
                    if created:
                        stats.ads_created += 1
                    else:
                        stats.ads_updated += 1
                stats.queries_processed += 1
            except SerpApiError as exc:
                logger.warning(
                    "competitors_google_serpapi_error",
                    extra={"query": query_str, "status": exc.status},
                )
                stats.errors.append({"query": query_str, "error": f"serpapi_{exc.status}"})
            except Exception as exc:  # noqa: BLE001
                logger.exception("competitors_google_query_failed", extra={"query": query_str})
                stats.errors.append(
                    {"query": query_str, "error": f"{type(exc).__name__}: {str(exc)[:180]}"}
                )
    finally:
        if own_client:
            await serpapi_client.__aexit__(None, None, None)

    logger.info("google_ads_refresh_done", extra=stats.as_dict())
    return stats
