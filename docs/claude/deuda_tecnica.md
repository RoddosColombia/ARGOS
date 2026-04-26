# Deuda técnica · ARGOS

Registro vivo de decisiones conscientes de diferir trabajo. Cada entrada incluye owner, prioridad, y phase objetivo para resolver.

Formato:

```markdown
## DT-XXX · Título

**Creada:** YYYY-MM-DD (Phase X / Build Y)
**Prioridad:** baja / media / alta / crítica
**Owner:** @nombre
**Phase objetivo para resolver:** Phase Y+N
**Estado:** pendiente / en-progreso / resuelto

### Contexto
### Por qué se difirió
### Trade-off aceptado
### Señales para re-evaluar
### Tags
```

---

## DT-001 · Backend sin Dockerfile · deploy vía Render UI con pip+uvicorn

**Creada:** 2026-04-22 (Phase 0 / Build 0.5 v2)
**Prioridad:** baja
**Owner:** @CEO
**Phase objetivo para resolver:** Phase 5+ (cuando scale y GraphRAG justifiquen containerización)
**Estado:** pendiente

### Contexto

Build 0.5 v1 incluyó `Dockerfile` multi-stage (python:3.11-slim, builder+runtime) + `render.yaml` blueprint + `.dockerignore`. El PR #4 falló en CI porque `.dockerignore` excluía `README.md` (ver ER-001). Se decidió simplificar por paridad operativa con SISMO V2, que corre en Render con buildpack nativo (Python auto-detectado, sin Docker).

### Por qué se difirió

1. **Overhead sin beneficio inmediato.** Para Phase 0 el backend es FastAPI + Motor + bcrypt · Render ejecuta con su buildpack Python nativo en ~40s vs multi-stage Docker ~90s (primer build).
2. **Paridad con SISMO V2.** Mismo estilo de deploy reduce carga cognitiva al equipo y permite que scripts operativos (rollback, logs) funcionen idéntico en ambos proyectos.
3. **Blueprint IaC prematura.** `render.yaml` impone disciplina de IaC pero agrega otro archivo que mantener sincronizado con la realidad de Render UI. En Phase 0 con 2 servicios simples, el setup manual en UI lleva 10 min.
4. **Docker smoke test en CI fallando** reveló complejidad accidental (`.dockerignore` pattern quirks) que no paga en este momento.

### Trade-off aceptado

- Deploy config vive en la UI de Render, no en el repo · requiere documentación disciplinada en `README.md` para que el CEO reproduzca manualmente.
- Sin reproducibilidad IaC: si se pierde la config en Render, se reconfigura leyendo el README.
- Sin `Dockerfile`: no hay forma de correr el backend idéntico a prod en local (en dev se usa uvicorn directo).

### Señales para re-evaluar

- Añadir un 3er servicio (Langfuse, worker Celery, MongoDB reemplazado por clúster propio) → IaC empieza a pagar
- Scale horizontal donde la reproducibilidad inter-instancia importe
- Onboarding de un 2do dev que no quiera configurar Python 3.11 local
- Migración a un provider distinto de Render (AWS, Fly) donde Dockerfile es el lingua franca

### Tags

#infra #docker #deploy #render

---

## DT-002 · Sin GitHub Actions deploy workflow · Render GitHub app es single-point-of-trigger

**Creada:** 2026-04-22 (Phase 0 / Build 0.5 v2)
**Prioridad:** baja
**Owner:** @CEO
**Phase objetivo para resolver:** Phase 5+ si se necesita control de deploy más allá del auto-push

### Contexto

Build 0.5 v1 incluía `.github/workflows/deploy.yml` con fallback vía `RENDER_DEPLOY_HOOK_*` secrets. v2 lo elimina · deploy lo maneja 100% la GitHub app de Render que auto-deploya en cada push a `main`.

### Por qué se difirió

- La app de Render es suficiente para Phase 0 · auto-deploy es el comportamiento esperado del equipo
- Un workflow de deploy adicional sin secrets configurados es no-op · ruido en el repo
- Reintroducirlo cuando haya pipelines multi-etapa (preview → staging → prod con manual approval gate)

### Trade-off aceptado

- Un solo botón "Deploy" vive en Render, no en GitHub
- Si Render GitHub app se desconecta silenciosamente (rare), los deploys quedan en pausa hasta que alguien lo note

### Señales para re-evaluar

- Necesidad de preview environments por PR (staging effímero)
- Gate de deploy manual (dry-run en CI, humano aprueba, push a prod)
- Deploy coordinado cuando ARGOS + SISMO V2 + admin web tengan dependencias versionadas

### Tags

#ci #deploy #render

---

## DT-007 · Classifier Haiku sin feedback loop · clasificaciones no evaluadas

**Creada:** 2026-04-26 (Phase 1 / Build 1.1)
**Prioridad:** media
**Owner:** @CEO + @backend
**Phase objetivo para resolver:** Phase 4+ (cuando llegue impact tracking en T+7)
**Estado:** pendiente

### Contexto

Build 1.1 introduce `HaikuProductClassifier` que decide qué items de MELI/FB se persisten en `products_catalog` y cuáles se descartan (emiten `scout.product.discarded`). Las decisiones del classifier son binarias: relevante=True/False con razón en texto.

**No hay mecanismo para evaluar la calidad de esas clasificaciones.** Si Haiku está descartando productos que sí eran relevantes, lo descubrimos solo mirando manualmente los eventos `scout.product.discarded` en MongoDB. No hay precision/recall medido, no hay sample re-clasificado, no hay alarma si la tasa de descartes diverge mucho de un baseline esperado.

### Por qué se difirió

- En Build 1.1 lo prioritario es ingerir datos reales filtrados (mejor que sin filtro). Tener feedback loop primero requeriría datos limpios, lo cual es circular.
- El feedback loop natural es Phase 4 (impact tracking): si una recomendación sale del Strategist y pega o no pega contra ventas reales, el classifier que dejó pasar/bloqueó los productos relevantes recibe señal indirecta.
- Antes de Phase 4, lo que hay es revisión manual del CEO sobre el catálogo · suficiente para sample.

### Trade-off aceptado

- Falsos negativos del classifier (productos relevantes marcados como no-relevantes) son invisibles en el flujo principal. Solo se descubren con auditoría manual de `scout.product.discarded`.
- Falsos positivos (productos no relevantes marcados como relevantes) ensucian `products_catalog` pero el Strategist los puede filtrar downstream con sus propios criterios.
- No hay versión-control del prompt del classifier · si se cambia el prompt, no hay forma de comparar antes/después contra un golden set.

### Señales para re-evaluar

- Phase 4 entra: ahí se construye el impact tracking y el feedback loop
- Tasa de descartes > 80% sostenida por > 3 días (anómalo · probablemente prompt mal calibrado)
- CEO reporta que "no llegan productos que esperaba ver" (señal cualitativa)
- Cantidad de listings en `products_catalog` no crece linealmente con frecuencia de ticks

### Mitigaciones activas

- Eventos `scout.product.discarded` con `reason` quedan en `argos_events` · auditables manualmente
- Cache local del classifier reduce llamadas Anthropic redundantes (~costo)
- `NoOpClassifier` fallback cuando no hay `ANTHROPIC_API_KEY` · degrada a "guarda nada" en vez de "guarda todo sin filtro" · evita contaminación silenciosa del catálogo

### Tags

#classifier #haiku #ml #feedback-loop #scout

---

## DT-006 · ✅ RESUELTO · Watch queries hardcoded en código (Build 1.0)

**Creada:** 2026-04-23 (Phase 1 / Build 1.0 · documentada retroactivamente como DT-006 por instrucción del CEO en Build 1.1)
**Prioridad:** media
**Owner:** @backend
**Phase objetivo para resolver:** Build 1.1
**Estado:** **resuelto en Build 1.1 (2026-04-26)**

### Contexto

Build 1.0 mantenía las 11 watch queries semilla del Scout como tupla constante en `argos/agents/scout/watch_queries.py`. Para activar/desactivar una query, ajustar prioridad, o agregar nuevas, se requería un PR + deploy.

### Solución aplicada (Build 1.1)

- Nueva colección Mongo `watch_queries` con schema `{workspace_id, query, source, activa, prioridad, created_at}` + índices `(workspace_id, query)` unique, `(workspace_id, activa)`, `(workspace_id, source)`
- Seed idempotente inserta las 11 queries originales con `$setOnInsert` (no sobrescribe ediciones manuales del CEO)
- Scout `tick()` ahora lee queries activas desde Mongo (con override opcional para tests)
- Endpoint `GET /api/v1/scout/watch-queries` (rol ceo) para listar queries del workspace
- Constante `WATCH_QUERIES` en código se mantiene como referencia documental + retrocompat para tests legacy

Edición de queries (toggle, prioridad, agregar): Build 1.2+ añade endpoints `POST/PATCH/DELETE`. Hasta entonces, edición vía Mongo directo.

### Tags

#scout #watch-queries #mongo #resolved

---

## DT-004 · APScheduler in-memory single-instance · no tolera escale horizontal

**Creada:** 2026-04-23 (Phase 1 / Build 1.0)
**Prioridad:** baja hasta Phase 3+ · media cuando haya 2+ instancias de backend en Render
**Owner:** @backend
**Phase objetivo para resolver:** Phase 3+ (cuando WhatsApp Agent obligue a escalar)
**Estado:** pendiente

### Contexto

Build 1.0 usa `AsyncIOScheduler` de APScheduler 3.x con jobstore **in-memory**. El backend corre en Render Starter (1 dyno) · un solo proceso ejecuta todos los jobs periódicos (hoy: `scout_tick` cada 6h en prod, 24h en dev).

### Por qué se difirió

- Escalar a Mongo-backed jobstore (`apscheduler.jobstores.mongodb.MongoDBJobStore`) suma complejidad y requiere cluster multi-instancia para pagar
- En Phase 1 no hay necesidad de alta disponibilidad del scheduler · si Render reinicia la instancia, el próximo tick ocurre a los 6h máximo (aceptable)
- Redis + Celery sería la alternativa "robusta" pero introduce 2 servicios nuevos (broker + worker pool) sin beneficio inmediato

### Trade-off aceptado

- Si Render corre 2+ instancias simultáneas (autoscale), cada una dispararía el tick → duplicación de escrituras a Mongo. Mitigado parcialmente porque `upsert_product` es idempotente a nivel source_id, pero se emitirían eventos duplicados al bus (viola espíritu de ROG-A6 "append-only" con semántica lógica única).
- Si el dyno cae a mitad de un tick, el trabajo se pierde silenciosamente. No hay persistencia del estado del job.
- Reemplazar APScheduler por Celery+Redis requeriría refactor del endpoint `POST /api/v1/scout/trigger` (hoy ejecuta in-process) y del lifespan de main.py.

### Señales para re-evaluar

- Autoscale de Render encendido (2+ instancias)
- Llegada de más jobs periódicos en Phase 2+ (briefing diario, impact tracking, price monitors de SKUs prioritarios cada 15 min)
- Necesidad de ver el estado de jobs desde UI (Flower o similar)
- Latencia del tick > 30s consistentemente (scheduler bloquea otros jobs)

### Mitigaciones activas

- `max_instances=1 + coalesce=True` en el job · evita overlap si un tick se retrasa
- Jobs son **idempotentes por diseño** (upsert, no insert) · ejecución duplicada no corrompe datos
- Endpoint manual `POST /api/v1/scout/trigger` (CEO/sistema) permite disparar ticks bajo demanda si el scheduler deja de funcionar

### Tags

#infra #scheduler #apscheduler #scale

---

## DT-003 · Sin runtime pinning fino (patch de Python) más allá de runtime.txt

**Creada:** 2026-04-22 (Phase 0 / Build 0.5 v2)
**Prioridad:** baja
**Owner:** @CEO
**Phase objetivo para resolver:** Phase 5+ o antes si aparece CVE en runtime

### Contexto

`runtime.txt` pinea `python-3.11.11`. No hay mecanismo automático para detectar cuando Python 3.11.12+ esté disponible con security patches.

### Por qué se difirió

- Dependabot / Renovate no cubren runtime.txt nativamente
- Bump manual mensual es suficiente para Phase 0

### Trade-off aceptado

- Ventana de vulnerabilidad hasta bump manual
- Aceptable porque el backend no procesa input no-sanitizado de terceros en Phase 0

### Señales para re-evaluar

- CVE crítico en Python 3.11.11
- Phase 3+ (WhatsApp webhooks aceptan input de terceros)

### Tags

#infra #security #runtime
