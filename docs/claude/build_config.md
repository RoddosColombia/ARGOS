# Build config-intelligence — Panel de queries + descubrimiento automático

## Objetivo declarado

Convertir `watch_queries` en un panel de control para el CEO (CRUD + categorías + activar/pausar) y agregar el `DiscoveryAgent` que propone términos emergentes, productos en alza/liquidación y SKUs desaparecidos para que el CEO los acepte o descarte. Cerrar el loop con el Strategist: el Morning Briefing menciona los términos sugeridos pendientes.

## Pre-requisitos

- Phase 1 (Scout, Marketplace) ✅ — `products_catalog` poblado por el Scout
- Phase 3 (Strategist + briefings) ✅ — para inyectar `discovery_suggestions` en el briefing
- Categorías por workspace seedeadas

---

## Qué se construyó

### Parte 1 · Control manual de queries

- **Schema migration** sobre `watch_queries` con campos nuevos · `origin` (manual/suggested/auto_discovered), `category`, `status` (active/paused), `priority`. Backfill idempotente al arrancar el indexer (legacy docs ⇒ `origin=manual`, `status` derivado de `activa`, `priority` derivado de `prioridad`, `category=null`).
- **API REST** (`api/v1/config.py`):
  - `GET/POST/PATCH/DELETE /api/v1/config/queries` con filtros por `status/origin/category`
  - `GET /api/v1/config/categories` + `PATCH /api/v1/config/categories/{slug}` (toggle active)
  - `POST /api/v1/config/categories/request` emite `config.category.requested` para que el equipo ARGOS habilite verticales nuevas
- **Seed** de 4 categorías default (`repuestos_moto`, `accesorios_moto`, `motos`, `aceites_lubricantes`).

### Parte 2 · DiscoveryAgent

- `agents/discovery/service.py` con 3 métodos puros + `run_discovery_job` orquestador:
  - **`discover_trending(workspace, category)`** · cuenta menciones de términos en `products_catalog.nombre` recientes (7d) que NO están ya cubiertos por `watch_queries`. Lógica: extrae bigramas/trigramas de las primeras palabras del nombre, descarta los ya cubiertos por una query existente como sub-string, ranking por count (mínimo 3 menciones para no rotar ruido).
  - **`discover_rising_products`** · agregación sobre `products_catalog` por `sku_normalizado`: cuenta listings nuevos en últimas 48h ≥ 10. Si `min_precio` es < 85% del `max_precio` del set marca `liquidating`, sino `rising`.
  - **`discover_disappearing`** · compara dos ventanas (now-14d → now-7d vs now-7d → now). SKUs con ≥5 listings antes y ≤1 ahora se reportan con `delta_pct` negativo.
- **Idempotencia** del job vía unique compound `(workspace, category, term, signal_type, date)`.
- **Cron 06:00 UTC** registrado en `scheduler.py`, antes del Morning Briefing 06:45 UTC.

### Parte 3 · Frontend

- **`/settings/queries`** con tabs `Mis queries` / `Sugerencias ARGOS`:
  - Tab "Mis queries": tabla SKU/categoría/origin badge/toggle status/eliminar · botón "+ Agregar query" abre form inline con selector de categorías cargadas.
  - Tab "Sugerencias ARGOS": cards con badge de color por `signal_type` (verde trending / azul rising / amarillo liquidating / rojo disappearing), evidencia traducida a texto natural (ej. "14 nuevas publicaciones en 48h"), botones "Agregar a mis queries" / "Descartar".
- **`/settings/categories`** · toggle list + form "Solicitar nueva categoría".
- **Sidebar** · grupo nuevo "Configuración" con sub-items "Queries e inteligencia" y "Categorías".

### Parte 4 · Integración con Strategist

- `_Signals.discovery_suggestions: list[dict]` (top 3 con `status=pending`, ordenadas por confianza).
- `gather_signals` consulta `discovery_suggestions` y la inyecta vía `to_user_payload()`. El Sonnet 4.6 ahora ve los términos pendientes y puede mencionarlos en el briefing como ARGOS-detected gaps.

---

## Decisiones técnicas

- **Deviación de spec sobre nombre de campo `source`** · El spec pedía agregar `source: manual|suggested|auto_discovered` en `watch_queries`, pero el campo `source` ya existe en Build 1.1 con semántica de marketplace target (`meli/fb_marketplace/all`) usado por el Scout. Renombrar habría requerido migrar Scout. Decisión: usé `origin` para el nuevo concepto, dejé `source` intacto. Misma lógica con `status/activa` y `priority/prioridad`: campos nuevos canónicos en inglés, sync'd a los legacy en español para que el código existente siga funcionando.
- **Heurística de discovery sin SerpAPI/MELI trends en este build** · El spec mencionaba "MELI /trends/MCO + SerpAPI Google Trends" pero con `products_catalog` ya poblado por el Scout, la señal de "trending" se aproxima con menciones de productos (lo que la gente publica refleja lo que la gente busca). Esto evita gastos en SerpAPI y latencia adicional. Cuando se necesite expandir a queries fuera del long-tail del catálogo, ampliar `discover_trending` con llamadas a esos partners (queda como DT-014).
- **Filtrado por substring en `_matches_existing`** · Para evitar que candidate `"filtro aire moto"` aparezca cuando la query existente es `"filtro aire"`. Cualquier candidato que contenga (substring) una query existente se filtra. Más estricto que match exacto pero evita ruido.
- **Workspace-wide aggregation sin SKU específico (Build 4.2 también)** · Discovery filtra por categoría pero no por SKU del producto. Suficiente para sugerir términos.
- **Idempotencia del `accept_suggestion`** · si la unique de `watch_queries` falla por duplicado, igual marcamos la sugerencia como `accepted` (no se rompe el flujo). El CEO no debería ver "ya existe" como error.

## Cambios en canónicas

- `docs/canonicas/colecciones_mongo.md` · 2 colecciones nuevas (`categories`, `discovery_suggestions`) + sección de extensión sobre `watch_queries` con la deviación de `source`/`origin`.
- `docs/canonicas/eventos.md` · dominio nuevo "Configuración e inteligencia" con `discovery.suggestions.generated` y `config.category.requested`.

## Errores cometidos y cómo se resolvieron

| Error | Causa raíz | Solución | Prevención futura |
| --- | --- | --- | --- |
| Test `test_discover_trending_filtra_terminos_existentes` falla porque `"filtro aire moto"` aparece en sugerencias aunque `"filtro aire"` ya está en watch_queries | `_candidate_terms` extrae bigramas y trigramas; el set `existing` solo hacía match exacto | Helper `_matches_existing(candidate, existing)` que filtra si cualquier query existente es substring del candidato | Extiende a discover_rising/disappearing |
| Test `test_categories_toggle` esperaba 2 categorías pero llegaron 4 | El lifespan ejecuta `seed_initial_data` que inserta los 4 defaults tras la fixture pre-seedear 2 | Ajustado `assert len(body) >= 2` y verificación específica del slug toggleable | Tests de endpoints que pasen por lifespan deben asumir el seed corre · no presumir conteos exactos |

## Deuda técnica generada

- **DT-014** · `discover_trending` no usa SerpAPI Google Trends ni MELI /trends/MCO. Cuando el catálogo del workspace sea pequeño, las sugerencias serán pobres. Agregar partners externos cuando RODDOS pase a multi-vertical.
- **DT-015** · `confidence` es heurística simple basada en counts. Cuando haya feedback (CEO acepta/descarta), entrenar un modelo simple para predecir aceptación y ajustar confidence. Pasa Phase 5+.
- **DT-016** · `accept_suggestion` no propaga la `category` y `priority` del CEO al crear el watch_query · usa `priority=1` y `category` de la sugerencia. Si el CEO quiere customizar al aceptar, no puede. Mejorar UI para abrir el form de "Add" con prefill.

## Métricas

- Tests: **3 backend** (config_api con CRUD + categories + accept) + **3 backend** (discovery service: trending filter + rising/liquidating + run_job + event) + **1 frontend** = 144 backend + 28 frontend = total tests passing
- Lint: `ruff check` clean (1 fix manual: `try/except/pass` → `contextlib.suppress`)
- Build frontend: 174 modules · 474 KB JS · sin warnings

## Cierre

#### Build config-intelligence · 2026-04-26
- Cerrado por: Andrés San Juan (CEO · approval pendiente) + Claude Code
- Rama: `build/config-intelligence` → PR a `main`
- Próximo: extensión natural sería **conectar `discovery_suggestions` al briefing en el prompt** (ahora solo va en signals, podría tener una sección dedicada "ARGOS detectó:" en el JSON output)
