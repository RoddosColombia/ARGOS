# Phase 1 — Marketplace MELI + Trends + Briefing v1 + SISMO Read + Impact Tracking

## Objetivo declarado
Primera fase funcional. Marketplace Agent consume MELI, Trends consume SerpAPI, Strategist genera briefing v1 diario, SISMO expuso 4 endpoints de lectura y ARGOS los consume. Impact tracking cierra el loop: recomendación aprobada hoy → medición automática en T+7 desde SISMO sales.

## Pre-requisitos
- Phase 0 cerrada con tag `phase-0-closed`
- SISMO V2 expuso endpoints /api/inventory/repuestos, /api/inventory/motos, /api/sales/daily, /api/loanbook/snapshot, /api/customers/{id}
- App reviews Meta y Google siguen en curso (no bloquean Phase 1)

## Builds incluidos
- **Build 1.0 — MELI API + Marketplace agent + Scout stub + primer ingest real** (adelantado por instrucción del CEO · integra parcialmente 1.1 y 1.3 sin Haiku)
- Build 1.1 — Scout con Haiku 4.5 · clasificación relevante/no-relevante + categorización jerárquica
- Build 1.2 — Trends Agent con SerpAPI
- Build 1.3 — Apify actor para FB Marketplace (antes era Scout · movido porque Haiku está en 1.1)
- Build 1.4 — Strategist Agent v1 (sin GraphRAG · eso llega Phase 5)
- Build 1.5 — Executive Agent + frontend /briefing
- Build 1.6 — Integración SISMO lectura · sync nightly
- Build 1.7 — Impact tracking · job que mide actual_impact en T+7 desde SISMO sales
- Build 1.8 — Morning Briefing diario v1 publicado a las 05:30
- Build 1.9 — Compliance Officer básico (solo caps spending · sin caps WhatsApp todavía)

## Decisiones arquitectónicas tomadas

### Build 1.0 · MELI + Marketplace + Scout stub + APScheduler (2026-04-23)

- **Sin SDK oficial de MELI · `httpx.AsyncClient` directo.** Los endpoints públicos (`/sites/MCO/search`, `/items/{id}`) responden bien sin OAuth. Evita una dep extra hasta que Build 1.5+ necesite datos privados de sellers. Wrapper `MeliClient` expone `search()` e `item()` con `asyncio.Semaphore(5)` para rate-limit self-imposed y `MeliError(status, msg)` para 404/429.
- **`sku_normalizado = "{source}:{source_id}"` (ej. `meli:MCO-12345`) en Build 1.0.** Agrupación semántica real (mismo repuesto en múltiples listings) llega en Build 1.1 con Haiku. Build 1.0 usa el SKU como identificador estable por-listing. Documentado en canónica `colecciones_mongo.md`.
- **`categoria` queda `""` · `categoria_meli_id` persiste raw.** Jerarquía `repuestos.frenos.pastillas` la llena Haiku en Build 1.1. Hint crudo disponible mientras tanto para queries de agrupación por categoría MELI.
- **Price change threshold ≥ 5% (absoluto).** Por debajo no emite `marketplace.price.changed` ni escribe en `products_history`. Threshold hardcoded en `PRICE_CHANGE_THRESHOLD_PCT`. Suficiente para Phase 1; Build 5+ puede hacer threshold dinámico por categoría/volatilidad.
- **`products_history` escribe solo cuando precio o stock cambian.** Evita inflar la colección con ticks redundantes (11 queries × 20 items × 4 ticks/día = 880 rows/día sin cambios · con filtro baja a ~50). Consultas analíticas se basan en los deltas reales.
- **APScheduler 3.x `AsyncIOScheduler` in-memory.** Cadencia prod 6h · dev 24h (para no gastar en local). `max_instances=1 + coalesce=True` evita overlap. DT-004 documenta las señales para migrar a Mongo-backed jobstore o Celery cuando haya autoscale horizontal.
- **Scheduler separado: `build_scheduler()` (construye, no arranca) + `start_scheduler()` (construye + start).** Tests usan `build_scheduler` para inspeccionar jobs sin necesitar event loop. Esta separación resolvió contaminación cross-test que rompía 13 tests post-scheduler en pytest-asyncio auto mode.
- **`ARGOS_DISABLE_SCHEDULER` env var** para apagar el scheduler en tests y en builds locales que no quieren spam de MELI. Default `false`. Tests fuerzan `true` en conftest.
- **`POST /api/v1/scout/trigger`** protegido por `require_role("ceo", "sistema")`. Returns stats del tick (queries procesadas, products detected/created/price_changed, errors por query). Retorna 503 si Mongo no está conectado (no degrada silenciosamente).
- **Scout stub sin Haiku.** Tick itera `WATCH_QUERIES` (11 queries semilla, incluye `repuestos TVS Raider 125` por instrucción del CEO) e invoca `upsert_product` con todos los resultados. Sin filtro semántico "relevante/no-relevante" · llega en Build 1.1.
- **Errores por query se aíslan en el tick.** Un 429 o un error de red en una query NO tumba las otras 10. `stats.errors` acumula por-query con `meli_429` / `TypeError: ...` como etiqueta. `queries_processed` solo cuenta las exitosas.
- **`publish_event` + helpers por dominio** (`publish_marketplace_product_detected`, `publish_marketplace_price_changed`). Los helpers validan schema del payload en el sitio donde se emite · más legible en los call sites que armar el dict inline.
- **Compatibilidad moto por regex sobre título** (`argos/agents/marketplace/categorizer.py`). 11 patrones para TVS Raider 125, Pulsar 200/180/150/135/NS 200, Boxer, Discover, NKD, CB 110, AKT. Heurística simple reemplazable por Haiku en Build 1.1.
- **Tests: 20 nuevos (4 meli client mockeado + 8 marketplace service con Atlas real + 3 scout service + 4 scout API + 1 scheduler).** Total backend: 47 unit + 20 nuevos = 67 tests passing.

## Cambios en canónicas

### Build 1.0
- `docs/canonicas/apis_externas.md` · MercadoLibre section actualizada: sin SDK, httpx directo, auth público (sin OAuth), notas de implementación apuntando a `argos/partners/meli/client.py`
- `docs/canonicas/eventos.md` · payloads refinados para `marketplace.product.detected` y `marketplace.price.changed` con los campos reales que emite el código
- `docs/canonicas/colecciones_mongo.md` · notas agregadas sobre convención `sku_normalizado` (Build 1.0 placeholder hasta Haiku) y `categoria` vacía (Build 1.1 la llena)

## Errores cometidos y cómo se resolvieron

| Error | Causa raíz | Solución | Prevención futura |
| --- | --- | --- | --- |
| 13 tests post-scheduler fallaban con "Event loop is closed" | `AsyncIOScheduler.start()` liga el scheduler al loop del test actual · cuando pytest-asyncio cierra el loop, referencias internas quedan colgadas y contaminan tests subsecuentes | Refactor: exponer `build_scheduler()` (sin `.start()`) y testear contra eso · `start_scheduler()` queda solo para producción (lifespan) | Ante dependencias "que quieren un event loop", separar construcción de arranque · los tests casi siempre pueden verificar el wiring sin runtime real |
| Assert `set(created.keys()) == set(col.ALL_BUILD_0_3)` rompió al extender `ensure_indexes` para Build 1.0 | Test demasiado estricto · comparaba igualdad en vez de "al menos contiene las de 0.3" | Cambio a `issubset` · tests futuros que agreguen colecciones no rompen este check | Para assertions sobre colecciones creadas por funciones monolíticas que crecen build a build, usar `issubset` / `issuperset` en vez de igualdad exacta |

## Deuda técnica generada

- **DT-004 APScheduler in-memory single-instance** (documentada en `docs/claude/deuda_tecnica.md`) · plan de migración a Mongo-backed jobstore o Celery+Redis cuando Render autoescale o llegue Phase 3
- **Categorización jerárquica (`categoria`)** queda vacía en Build 1.0 · Build 1.1 con Haiku la llena
- **Agrupación real de SKUs equivalentes** (un mismo filtro aire en 10 listings distintos) depende de Haiku · hoy cada listing es un row independiente en `products_catalog`
- **`WATCH_QUERIES` es lista estática en código** · Build 1.1 mueve a colección Mongo `scout_watch_queries` para permitir edición sin deploy y activación por workspace

## Métricas de la fase
- Briefing diario publicado 7/7 días consecutivos: ⬜
- SISMO sync nightly sin fallos durante una semana: ⬜
- Al menos 5 recomendaciones generadas · 3 aprobadas · 2 medidas con actual_impact: ⬜
- Hit rate inicial capturado (sample pequeño, pero baseline): ⬜

## Aprendizajes
(a llenar al cierre)

## Cierre
- Fecha cierre: _pendiente_
- Cerrado por: _pendiente_
- PR final: _pendiente_
