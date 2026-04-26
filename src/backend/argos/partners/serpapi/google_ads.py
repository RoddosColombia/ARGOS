"""Wrapper de búsqueda en Google Ads Transparency Center vía SerpAPI.

Endpoint subyacente:
    GET https://serpapi.com/search.json?engine=google_ads_transparency_center&text=KEYWORD&region=CO&api_key=...

Output relevante (puede variar entre versiones del engine SerpAPI):
- `ad_creatives`: lista de ads · cada uno con `creative_id`, `advertiser_name`,
  `format` (TEXT/IMAGE/VIDEO), `first_shown`, `last_shown`, `creative_text` o
  `headline`, `destination_url`.
- Aliases observados en respuestas: `ads`, `creatives`, `text_ads`, `image_ads`.

El módulo expone una sola función `search_google_ads_transparency(keyword, ...)`
que devuelve la lista cruda de ads para que el agent normalice (separación de
responsabilidades · este módulo sólo conoce el contrato HTTP, no el schema
interno de ads_library).
"""
from __future__ import annotations

import logging
from typing import Any

from argos.partners.serpapi.client import DEFAULT_GEO, SerpApiClient

logger = logging.getLogger("argos.partners.serpapi.google_ads")


async def search_google_ads_transparency(
    keyword: str,
    *,
    client: SerpApiClient,
    region: str = DEFAULT_GEO,
) -> list[dict[str, Any]]:
    """Devuelve la lista de ad_creatives para `keyword` · `[]` si no enabled.

    Tolera variantes del shape de respuesta de SerpAPI · busca la lista bajo
    múltiples claves comunes y devuelve la primera no vacía.
    """
    if not client.enabled:
        logger.warning("google_ads_transparency_skipped_no_key", extra={"keyword": keyword})
        return []

    raw = await client.google_ads_transparency(keyword, region=region)
    if not isinstance(raw, dict):
        return []

    for key in ("ad_creatives", "ads", "creatives", "text_ads"):
        creatives = raw.get(key)
        if isinstance(creatives, list) and creatives:
            return creatives
    return []
