# Phase 2 — Meta Ad Intelligence + Score Engine

## Objetivo declarado

Inteligencia competitiva profunda (Meta Ad Library, Google Transparency, social listening) + clonación del Score Engine de la web admin como microservicio interno de ARGOS.

## Pre-requisitos

- Phase 1 completa (Scout, Marketplace, Trends, Alerts) ✅
- `APIFY_API_TOKEN` configurado en Render env vars (CEO · pendiente)
- `RISKSEAL_API_KEY` para Score Engine (CEO · Phase 2.5+)

## Builds incluidos

- **Build 2.1 — Meta Ad Library scraping (Apify) + vista /competitors** ✅
- Build 2.2 — Google Ads Transparency via SerpAPI (futuro)
- Build 2.3 — TikHub social listening (movido a Phase 7)
- Build 2.4 — Score Engine clon · skeleton + endpoints
- Build 2.5 — RiskSeal integration en Score Engine
- Build 2.6 — Score Engine XGBoost Capa 1
- Build 2.7 — Score Engine Claude Sonnet Capa 2

## Decisiones arquitectónicas tomadas

### Build 2.1 · Meta Ad Library (Apify) + vista /competitors (2026-04-26)

- **Actor `apify~facebook-ad-library-scraper`** elegido sobre `igolaizola/facebook-ad-library-scraper` por instrucción del CEO. Apify-mantenido es más estable a largo plazo (versiones, soporte) aunque puede ser más caro por run que el de igolaizola. Si el costo se sale de presupuesto, evaluar fallback en Build 2.2.
- **Reuso de `ApifyClient`** (Build 1.1) extendido con `fb_ad_library_search()`. Mismo patrón: skip silencioso sin token · context manager · 401/429 → `ApifyError`. Mantener un cliente compartido evita duplicación y permite que el reintento/timeout se ajuste centralmente.
- **`apify~facebook-ad-library-scraper` accepta `searchTerms: [str]` como lista** (no string · diferencia con FB Marketplace scraper que toma `search: str`). El cliente expone solo `query: str` y arma `[query]` internamente. Si en el futuro se necesita batch multi-keyword en una sola corrida, agregar variante `fb_ad_library_search_batch(queries: list[str])`.
- **Schema `ads_library` adoptado en spec del CEO (Build 2.1)** difiere parcialmente del schema legado en `colecciones_mongo.md`. Renombres: `platform → plataforma`, `copy_text → copy_texto`, `primera_deteccion → fecha_inicio` (con `primera_deteccion` ahora referencia al timestamp de upsert), `activo_actualmente → activo`. Campos nuevos: `anunciante`, `copy_titulo`, `url_landing`, `fecha_fin`, `formato`, `fuente_query`. Canónica actualizada al spec nuevo · campos legacy `competitor_id` y `sku_referenciado` se mantienen para futuro (Phase 2.5+).
- **`competitors.ad.detected` evento nuevo** distinto del `competitor.ad.detected` legacy (sin `s` en competitor). Rationale: el evento legacy declaraba payload `{competitor_id, ad_id, copy, creative_url}` que asume FK a colección `competitors` (no existe todavía). El nuevo Build 2.1 emite `{plataforma, ad_id_externo, anunciante, copy_titulo, fuente_query, durabilidad_dias, formato}` que es self-contained (Strategist puede consumir sin joins). Cuando aparezca colección `competitors`, mappear `anunciante → competitor_id` con upsert.
- **Eventos solo en primera detección, no en re-detection.** `upsert_meta_ad` retorna `(created, ad_id_externo)`; el evento se emite SOLO si `created=True`. Las re-detecciones del mismo `ad_id_externo` actualizan `ultima_deteccion + updated_at + copy_texto/copy_titulo/etc.` pero no producen ruido en el bus. Razón: el actor scrapea ~30 ads × 11 watch queries × 2 corridas/día = 660 emisiones/día si emitiéramos en cada upsert, mucho ruido para Strategist.
- **`fecha_fin` parser tolerante a formatos múltiples.** Apify retorna `null`, ISO 8601 con `Z`, ISO sin tz, epoch seconds, o epoch ms. `_parse_date()` discrimina por tipo + heurística numérica (>10B = ms). Tests cubren los formatos comunes pero el actor puede sorprender con otro · si aparece, agregar branch + test.
- **Detector de formato por fallback** (`_detect_formato`) busca en `creative_type`, `format`, `ad_creative_type` en orden, hace lower + sustring match para `video/carousel/image`. Fallback a `video_url` o `video` field present. Si nada → `unknown`. No usar Haiku para esto · es heurística string simple que no justifica el cost.
- **Scheduler: `meta_ads_refresh` cada 12 horas** vs el `scout_tick` de 6h. Ad Library refresh es más caro (Apify por run) y los ads no rotan tan rápido como precios MELI. 12h da 2 runs/día = ~440 unique ad-detections/día asumiendo 20 nuevos por corrida.
- **`only_active` query param** en `GET /api/v1/competitors/ads`. Razón: el CEO normalmente quiere ver "qué están corriendo HOY los competidores" (filtro) pero también necesita historial para análisis de durabilidad ("qué ads sobreviven >30 días = están funcionando"). Toggle UI lateral.
- **Sin endpoint `POST /api/v1/competitors/ads/trigger` todavía.** Build 2.1 confía en el cron de 12h · si CEO quiere disparo manual, agregar análogo a `POST /api/v1/scout/trigger` en Build 2.2.
- **Vista `/competitors` con TanStack Query refetchInterval 10min.** Más frecuente que el cron de 12h · el frontend siempre tiene datos frescos relativos al último write a Mongo aunque el scrape no haya corrido. `refetchIntervalInBackground=false` para no spam pestañas inactivas.
- **Sidebar item "Competidores" enabled · Phase 2.** Tercer módulo live (después de Marketplace y Trends & Alertas). Sidebar empieza a poblarse · refactor a submenu cuando lleguen 5+ items live.

## Cambios en canónicas

### Build 2.1
- `docs/canonicas/colecciones_mongo.md` · sección `ads_library` reescrita al schema Build 2.1 (renombres + campos nuevos + nota sobre legacy)
- `docs/canonicas/eventos.md` · evento nuevo `competitors.ad.detected` (legacy `competitor.ad.detected` queda marcado como tal)
- `docs/canonicas/apis_externas.md` · sección Apify expandida con actor Build 2.1 `apify~facebook-ad-library-scraper` y `competitors.ad.detected` en eventos producidos

## Errores cometidos y cómo se resolvieron

| Error | Causa raíz | Solución | Prevención futura |
| --- | --- | --- | --- |
| Test frontend `getByText(/activo/i)` matcheaba múltiples elementos | El header de columna "Días activo" colisiona con el badge "🟢 activo" cuando se busca con regex insensitive | Match exacto al emoji+texto del badge: `getByText(/🟢 activo/)` | Para badges con texto común, incluir el emoji o data-testid en el selector · NUNCA usar regex permisivo en headers de tabla |

## Deuda técnica generada

- **Sin tests del scheduler para `meta_ads_refresh` job** · build_scheduler tests cubren scout_tick + trends + price_alert pero el nuevo job se valida solo por wiring (import en main.py). Aceptable para Build 2.1 · agregar test cuando se haga refactor del scheduler.
- **Frontend `CompetitorsPage` no soporta paginación** · limit=50 hardcoded. Para workspaces con >50 ads/keyword × 11 keywords = 550+ ads, el dashboard pierde datos. Refactor a infinite scroll o paginación cuando llegue.
- **Sin filtro por `fuente_query` en endpoint** · útil para debugging ("qué ads salieron por la query X"). Agregar como query param opcional en Build 2.2.
- **`anunciante` no se normaliza** · "Repuestos Bogotá Online" y "REPUESTOS BOGOTÁ ONLINE" son docs distintos en Mongo · cuando aparezca colección `competitors` con dedup canónico, hacer mapeo.

## Métricas de la fase

- Tests Build 2.1: 7 backend (+6 nuevos en test_meta_ads_service · +1 test_competitors_api) + 2 frontend
- Total acumulado: 94 backend + 18 frontend = 112/112
- Lint: ruff limpio · tsc limpio · vite build sin warnings (168 modules · 434 KB JS)

## Cierre

### Build 2.1 · 2026-04-26
- Cerrado por: Andrés San Juan (CEO · approval pendiente) + Claude Code
- Rama: `phase-2/build-2.1-meta-ad-intelligence` → PR a `main`
- Próximo build: **2.4** — Score Engine skeleton (clon del admin web)
