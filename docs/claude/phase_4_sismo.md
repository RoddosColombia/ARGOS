# Phase 4 — Integración SISMO V2 (lectura)

## Objetivo declarado

Conectar ARGOS al ERP existente (SISMO V2) en modo read-only para que el Strategist tenga contexto de inventario, ventas y comportamiento de pago sin duplicar datos. ROG-A11 exige aislamiento de credenciales: la key de lectura de SISMO es exclusiva para ARGOS y nunca cruza al admin web.

## Pre-requisitos

- Phase 1, 2, 3 completas ✅
- `SISMO_API_URL` + `SISMO_API_KEY` provistos por el CEO desde el admin de SISMO V2 (scope read-only)
- Endpoints `/api/inventory/repuestos`, `/api/inventory/slow_movers`, `/api/sales/daily` expuestos en SISMO V2 (Build 14+)

## Builds incluidos

- **Build 4.1** — Cliente + agente + sync job + endpoint API + vista frontend
- (futuros) 4.2: ventas diarias · 4.3: loanbook read · 4.4: cobranza orchestrator (RADAR)

---

## Build 4.1 · SISMO V2 lectura · inventario

### Qué se construyó

- **Cliente async** · `argos/partners/sismo/client.py` con `SismoClient` (httpx · context manager · skip silencioso sin `SISMO_API_URL`+`SISMO_API_KEY`). Parser defensivo `_coerce_list` que acepta `[...]` directo o `{items|data|results: [...]}` para tolerar variaciones del shape de SISMO sin romper.
- **Agent** · `argos/agents/sismo/service.py` con `SismoAgent` (wrapper read-only) y `sync_sismo_inventory_job(db, workspace_id, agent)`. Normaliza items con `_normalize_inventory_item` (acepta naming sku/codigo, stock/existencias, precio/precio_venta, dias_inventario/dias_sin_rotacion), marca `is_slow_mover` localmente cuando `dias_inventario >= 45` (`SLOW_MOVER_DAYS_THRESHOLD`), upsert idempotente por `(workspace_id, sku, fecha_sync_date)`. Emite `sismo.inventory.synced` con `{total_skus, slow_count}`.
- **Colección nueva** · `sismo_inventory` con 3 índices (unique compound + sort by fecha_sync + slow_movers filter).
- **Scheduler** · `_sismo_sync_job` registrado con `IntervalTrigger(hours=6)` · cuatro snapshots por día · idempotencia garantiza que sólo el primero del día UTC inserta, los siguientes update.
- **Endpoint API** · `GET /api/v1/sismo/inventory?type=all|slow_movers&limit=N` (require_role ceo). Resuelve el `fecha_sync_date` más reciente del workspace y devuelve `{fecha_sync_date, type, items, total}`. NO llama a SISMO en runtime.
- **Strategist enriquecido** · `gather_signals` ahora incluye `inventory_summary` (totales del último snapshot) + top 10 `slow_movers` ordenados por `dias_inventario` desc. El LLM recibe estos campos en el `to_user_payload` y puede generar acciones de liquidación con contexto real de stock.
- **Frontend** · `SismoPage.tsx` con toggle `Todos/Slow movers (≥45 días)`, tabla con SKU/nombre/stock/precio/días/badge slow mover, formato COP. Refresh cada 5 min. Sidebar item "Inventario SISMO" enabled.

### Decisiones técnicas

- **Doble fuente para slow_movers** · La API expone `/api/inventory/slow_movers` pero ARGOS deriva `is_slow_mover` localmente desde `dias_inventario >= 45` para evitar dos roundtrips. Si SISMO cambia el threshold, ARGOS aplica el suyo (consistencia local). Cuando se quiera filtrar lo que SISMO marca, `SismoAgent.get_slow_movers()` está disponible pero el sync job no lo usa.
- **Snapshot por fecha (no historial granular)** · `fecha_sync_date` es `YYYY-MM-DD`. Esto significa que el último sync del día UTC sobreescribe a los anteriores. Trade-off intencional: histórico día a día para análisis de tendencia (Phase 4.2+) vs simplicidad ahora. Si en el futuro se necesita "stock a las 10am vs 2pm", agregar campo `fecha_sync_hour` y bumpear el unique index.
- **`async with self._client` no recrea cliente pre-inyectado** · `SismoClient.__aenter__` checa si `_client` ya existe (caso de tests con `httpx.MockTransport`) y sólo crea uno nuevo si no. `_owns_client` flag controla si `__aexit__` debe cerrarlo. Sin esto, los tests con `MockTransport` se rompían porque el agent reentraba el context manager y sustituía el mock por una conexión real.
- **Skip silencioso doble** · El `SismoClient.enabled = bool(url and key)` y `SismoAgent.enabled` lo propaga · `sync_sismo_inventory_job` checa `agent.enabled` y devuelve `SyncStats(enabled=False)` sin tocar Mongo. Permite CI sin SISMO real y entornos dev sin acceso al ERP.
- **`_get` retorna `None` (no `[]`) para señalar "no enabled"** · Distingue entre "API respondió lista vacía" y "no consultamos por falta de creds". `_coerce_list(None) → []` colapsa ambos casos en la API pública.

### Cambios en canónicas

- `docs/canonicas/colecciones_mongo.md` · sección nueva `sismo_inventory` con schema completo, 3 índices, lifecycle (skip silencioso, consumido por Strategist).
- `docs/canonicas/eventos.md` · `sismo.inventory.synced` actualizado a payload real (`{total_skus, slow_count}`) y productor `sismo_agent` (no `sismo_sync` legacy).
- `docs/canonicas/apis_externas.md` · sección nueva "SISMO V2" con endpoints, auth, fallback, dueño.
- `.env.example` · `SISMO_API_URL` + `SISMO_API_KEY` agregados con nota ROG-A11.

### Errores cometidos y cómo se resolvieron

| Error | Causa raíz | Solución | Prevención futura |
| --- | --- | --- | --- |
| Test `test_sync_job_persiste_inventario_y_marca_slow_movers` falla con `SismoError: http_error: ConnectError` aunque uso `httpx.MockTransport` | `SismoClient.__aenter__` siempre creaba un nuevo `httpx.AsyncClient`, sobreescribiendo el mock pre-inyectado en `client._client` | Hacer que `__aenter__` sólo construya cliente si `self._client is None` · introducir flag `_owns_client` para que `__aexit__` no cierre clientes inyectados desde fuera | Patrón aplicable a cualquier wrapper httpx con context manager · documentar en `errores_recurrentes.md` |
| `E501 Line too long` en literales de fixtures con dicts en una línea | Habituarse a la regla de 120 chars en pyproject.toml | Romper el dict en multiline con 4 keys por línea | — |

### Deuda técnica generada

- **Sin `sismo.sales.daily.synced`** · Build 4.1 sólo trae inventario. Ventas diarias (`/api/sales/daily`) ya existe en el cliente pero no hay job ni colección. DT-010 · debe llegar en Build 4.2 (necesario para hit_rate de recomendaciones tipo `pricing_change` con datos reales en lugar de sólo `marketplace.price.changed` events).
- **Sin `loanbook` read** · ROG-S2 requiere derivar `score_comportamental A+→E` de cuotas pagadas/vencidas en SISMO V2 para el bypass del flujo F3 (cliente RODDOS con historial positivo). Pendiente Build 4.3.
- **Sin retry/backoff en `SismoClient`** · Si SISMO 503 o timeout, el sync del día se pierde silenciosamente (logger.exception en scheduler wrapper). Aceptable porque `IntervalTrigger(hours=6)` da 4 chances diarios, pero en Build 4.2 agregar `tenacity` con exponential backoff cuando empiece a doler.
- **`is_slow_mover` se calcula en agent, no se persiste el threshold usado** · Si en el futuro RODDOS quiere cambiar el umbral a 60 días, los snapshots viejos seguirán con `is_slow_mover` calculado a 45d. Aceptable mientras el threshold no cambie · si cambia, agregar `slow_mover_threshold_used: int` al doc.

### Métricas de la fase

- Tests Build 4.1: **7 backend** (4 client + 3 service) + **1 frontend** (SismoPage.test.tsx)
- Total acumulado: **137 backend + 26 frontend = 163/163 passing**
- Lint: `ruff check` clean (1 fix manual de E501 en fixtures)
- Build frontend: 172 modules · 459 KB JS · sin warnings

### Cierre

#### Build 4.1 · 2026-04-26
- Cerrado por: Andrés San Juan (CEO · approval pendiente) + Claude Code
- Rama: `phase-4/build-4.1-sismo-integration` → PR a `main`
- Próximo build: **4.2** — sync de ventas diarias (`/api/sales/daily`) + colección `sismo_sales_daily` + integración con hit_rate de recomendaciones

---

## Build 4.2 · Ventas diarias SISMO + hit_rate real

### Qué se construyó

- **Sync de ventas diarias** · `sync_sismo_sales_daily_job(db, workspace_id, fecha=None, agent=None)` en `agents/sismo/service.py`. Default `fecha = ayer UTC` (job corre 01:00 UTC → procesa el día completo anterior). Idempotente por `(workspace_id, date, sku)` con upsert. Normalización defensiva con `_normalize_sales_item` (acepta sku/codigo, units_sold/unidades/cantidad, revenue/total/monto, date/fecha, channel/canal). Emite `sismo.sales.daily.synced`.
- **Colección `sismo_sales_daily`** · 3 índices (unique compound + sort by date + por SKU para queries del impact tracker).
- **Cron 01:00 UTC** · `_sismo_sales_sync_job` registrado en `scheduler.py` con `CronTrigger(hour=1, minute=0)` · llega antes del morning briefing (06:45 UTC) para que las recomendaciones del día tengan ventas frescas en el contexto futuro.
- **Impact tracker enriquecido (Build 4.2)** · Para recomendaciones con `type ∈ {pricing_change, promo_launch}`, `evaluate_pending_recommendations` ahora llama a `_aggregate_real_sales_window(db, workspace_id, executed_at, window_days=7)` que agrega `sismo_sales_daily` en la ventana T..T+7 y devuelve `{units_sold, revenue_cop, days_with_data, sku_count, window_start, window_end}`. Si hay datos, `actual_impact` se persiste con `metric="units_sold_and_revenue"` + métricas reales en lugar del placeholder cualitativo. El `hit_rate_contribution` heurístico se preserva como `actual_impact.hit_rate_heuristic` para auditoría.
- **`_generate_learning` enriquecido** · Recibe ahora `sales_metrics` opcional. Si vienen datos de SISMO, los inyecta en el prompt a Sonnet 4.6 con un bloque "Ventas reales SISMO en ventana 7d post-ejecución" · el modelo argumenta con números concretos en la reflexión.
- **Endpoint API** · `GET /api/v1/sismo/sales?date=YYYY-MM-DD&sku=optional&limit=N` (require_role ceo). Si `date` no se pasa, resuelve el último día con datos del workspace. Devuelve `{date, sku, items, totals: {units_sold, revenue_cop, count}}`. NO llama a SISMO en runtime.
- **Frontend** · `SismoPage` refactorizada con tabs `Inventario` / `Ventas`. La tab Ventas muestra 3 cards (Fecha, Unidades, Revenue) + tabla SKU/Unidades/Revenue/Canal. Refresh 5 min.

### Decisiones técnicas

- **Job corre 01:00 UTC, no medianoche** · Da margen de 1h para que SISMO termine de cerrar el día (timezone Bogotá, GMT-5). Si lo corriéramos a 00:00 UTC podríamos pegarle al cierre antes de que SISMO procese ventas tarde.
- **`actual_impact` schema cambió** para `pricing_change`/`promo_launch`** · La metric pasa de `qualitative` (Build 3.3) a `units_sold_and_revenue` cuando hay datos · campos nuevos: `units_sold`, `revenue_cop`, `days_with_data`, `window_start`, `window_end`, `hit_rate_heuristic`. **Backward-compatible**: el frontend de Recommendations sólo lee `hit_rate_contribution` y `learning` que siguen poblándose. Si se quiere mostrar units_sold en `RecommendationsPage` después, leer `actual_impact.units_sold` con fallback.
- **Workspace-wide aggregation, no por SKU** · La rec actualmente no captura `sku_affected` (Build 3.3 derivaba el `type` por regex pero no extraía SKU del action_description). Por ahora `_aggregate_real_sales_window` suma todas las ventas del workspace en la ventana — útil cuando la rec es de mercado general (ej. "bajar precio aceites" sin SKU específico). Future Build 4.3+ podrá extraer SKUs explícitos del Strategist y filtrar.
- **`hit_rate_heuristic` preservado en actual_impact** · No reescribimos el hit_rate: si la heurística marca 1.0 pero las ventas reales fueron flat, el `learning` de Sonnet pega más fuerte la disonancia ("hit_rate=1.0 pero solo 3 unidades vendidas en 7d sugiere que el evento fue un competidor sin tracción real").

### Cambios en canónicas

- `docs/canonicas/colecciones_mongo.md` · sección nueva `sismo_sales_daily` con schema, 3 índices, lifecycle.
- `docs/canonicas/eventos.md` · `sismo.sales.daily.synced` actualizado a payload real (`{date, sales_count, units_total, revenue_total_cop}`) y productor `sismo_agent`.

### Errores cometidos y cómo se resolvieron

Sin errores nuevos en Build 4.2. Los patrones aprendidos en 4.1 (httpx MockTransport pre-inyectado, parser defensivo, skip silencioso) se reutilizan limpiamente.

### Deuda técnica generada

- **Sin SKU específico en recomendaciones** · `actual_impact` agrega ventas a nivel workspace. Si la rec dice "bajar precio Aceite Motul a $52K", el agregado incluye también ventas de pastillas, cascos, etc. Aceptable porque la rec suele mover toda una categoría, pero queda DT-011 para que el Strategist (Build 4.3+ o 5.0) extraiga `sku_affected` explícito en el JSON de output.
- **`channel` se pierde en el agregado del impact tracker** · `_aggregate_real_sales_window` suma todos los canales · si SISMO devuelve granularidad por canal (tienda/whatsapp/web), no se aprovecha en la decisión "promo funcionó en WhatsApp pero no en tienda". DT-012 · agregar breakdown por canal en futura iteración del tracker.
- **Sin retry/backoff en `sync_sismo_sales_daily_job`** · si SISMO 503 al 01:00 UTC, perdemos el día. Aceptable porque es un job diario con bajo costo de retry manual, pero idealmente reintentar 2-3 veces con exponential backoff o re-correr el día siguiente desde el cron de inventario (que ya pasa cada 6h). DT-013.

### Métricas de la fase

- Tests Build 4.2: **4 backend** (3 sales sync + endpoint + 1 impact tracker con sismo_sales_daily) + **1 frontend** (tab Ventas en SismoPage)
- Total acumulado: **141 backend + 27 frontend = 168/168 passing**
- Lint: `ruff check` clean
- Build frontend: 172 modules · 463 KB JS · sin warnings

### Cierre

#### Build 4.2 · 2026-04-26
- Cerrado por: Andrés San Juan (CEO · approval pendiente) + Claude Code
- Rama: `phase-4/build-4.2-sismo-sales` → PR a `main`
- Próximo build: **4.3** — loanbook read (deriva `score_comportamental A+→E` para bypass del flujo F3) o **4.4** RADAR cobranza orchestrator
