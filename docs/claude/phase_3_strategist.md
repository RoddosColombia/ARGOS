# Phase 3 — Strategist + Executive + WhatsApp Agent

## Objetivo declarado

Cerebro de decisión (Strategist con Sonnet 4.6) + interfaz operativa al CEO (Executive con dashboard /briefing) + canal comercial conversacional (WhatsApp Agent en builds posteriores).

## Pre-requisitos

- Phase 1 completa (Scout, Marketplace, Trends, Alerts) ✅
- Phase 2 completa (Competitors Meta+Google, Social Listening) ✅
- `ANTHROPIC_API_KEY` en Render env vars (CEO · pendiente · sin la key el job se skip silencioso)
- Mercately + Wava ready para Builds 3.5+ (WhatsApp Agent)

## Builds incluidos

- **Build 3.1 — Morning Briefing (Strategist + Executive + vista /briefing)** ✅
- Build 3.2 — Recomendaciones de pricing (Strategist · approval gate)
- Build 3.3 — Recomendaciones de inventario
- Build 3.4 — WhatsApp Agent skeleton + Mercately webhook
- Build 3.5 — KYC conversacional (WhatsApp Flows)
- Build 3.6 — Cotizador visual (Claude vision)
- Build 3.7 — Flujo F1 (onboarding) + F2 (venta moto Crédito RDX)

## Decisiones arquitectónicas tomadas

### Build 3.1 · Morning Briefing (2026-04-26)

- **Modelo del Strategist: Sonnet 4.6 · NO Opus 4.7.** modelos_llm.md original recomendaba Opus para Strategist por "calidad > velocidad en producto estrella diario". Build 3.1 arranca con Sonnet por costo (5x más barato por output token) y porque el razonamiento sobre input estructurado (JSON de signals) no requiere la profundidad de Opus. El CEO puede pedir upgrade a Opus en Build 3.2+ si la calidad cualitativa del briefing es insuficiente · canary contra dataset de briefings reales antes de cambiar.
- **Prompt caching agresivo en system prompt.** SYSTEM_PROMPT del Strategist ~9KB con contexto profundo de RODDOS, productos canónicos, marcas relevantes, competidores identificados, y 2 ejemplos de calibración (día agresivo + día estable). `cache_control: {"type": "ephemeral"}` en el bloque system. Con 1 corrida/día, el cache no se aprovecha mucho — el valor real es cuando el job corra cada hora (Phase 5+) o cuando se pidan briefings ad-hoc en horario no planeado.
- **Output JSON estricto · `MorningBriefing` dataclass.** Strategist devuelve JSON con shape exacto: `{fecha, mercado_24h, acciones_del_dia[], estado_mercado}`. Parser tolerante: strip de markdown fences (Claude a veces los envuelve), default de prioridad inválida → "Media", cap a 3 acciones (ROG inamovible · "MÁXIMO 3 acciones del día"). Si parse falla → briefing degradado con `estado_mercado="no se pudo generar"` y signals nativos en mercado_24h (no falla el job).
- **Separación Strategist · Executive.** El Strategist solo razona (entrada signals → salida MorningBriefing JSON). El Executive persiste, emite eventos, y futuro: maneja approval gates en UI. Razón: facilita testing (mockear Strategist sin tocar Mongo) y futuras iteraciones (intercambiar el modelo del Strategist sin tocar el flujo de publicación).
- **`gather_signals` separado de la generación** · permite override en tests (`signals=_Signals()` vacío) y futuros endpoints de "generar briefing ad-hoc con signals custom" (Build 3.2+ explora esto). Recolecta últimas 24h de: products_catalog, marketplace.price.changed events, marketplace.price.alert events, keywords con spike, ads_library nuevos, social_accounts nuevos. Cada query con limit + projection para no traer payloads enormes a memoria.
- **`run_morning_briefing` como entrypoint del job** · `Executive` orquesta `Strategist.generate` + `Executive.publish_briefing`. Diseño "happy path" sin retry · si Anthropic está caído, briefing del día queda con estado_mercado="API error" pero NO se cancela el job (siguiente día reintenta naturalmente). En prod, Render Persistent Disk + retry con exponential backoff es overkill para Build 3.1 — DT futura si la disponibilidad de Anthropic genera problemas.
- **Idempotencia por (workspace_id, fecha) unique.** Re-runs del mismo día actualizan el doc · no duplican. El evento `briefing.published` SÍ se emite en cada upsert (audit trail completo · si el Strategist generó dos briefings del mismo día con outputs distintos, el bus tiene ambos eventos aunque la colección solo tenga el último). Acepted trade-off: bus es append-only (ROG-A6), colección refleja "última verdad".
- **Empty state explícito en frontend** cuando endpoint devuelve 404 (sin briefing del día). Mensaje sugiere que el job corre 06:45 UTC + nota explícita de que sin `ANTHROPIC_API_KEY` configurada el job es no-op. Decisión UX: en vez de loading infinito o error genérico, comunicar al CEO el estado real ("¿por qué no veo briefing?").
- **`PrioridadBadge` con paleta semántica** · Alta=red, Media=amber, Baja=ink. NO uso emerald (verde) porque "Baja" no es "buena", solo "menos urgente". Ink (gris) comunica neutralidad mejor. Trade-off vs emerald: pierde el contraste verde-amarillo-rojo del semáforo · gana neutralidad para no presionar al CEO a "hacer algo" cuando el briefing solo dice "vigilar inventario".
- **Briefing como PRIMER ítem del sidebar** (encima de Marketplace). Razón: es el "morning ritual" del CEO · debe estar en el primer click. Marketplace, Trends, etc. son módulos de inspección · Briefing es módulo de acción del día.
- **`logger.info("briefing_published", extra={...})` debe evitar keys reservadas de LogRecord.** Inicialmente usé `extra={"created": True}` que colisiona con `LogRecord.created` (timestamp built-in de Python logging). Renombrado a `was_created`. Documentado en errores recurrentes · cualquier helper que loguee con extra keys debe consultar la lista de reservadas (created, name, msg, levelname, etc.).

## Cambios en canónicas

### Build 3.1
- `docs/canonicas/colecciones_mongo.md` · sección nueva `briefings` con schema completo (fecha key, mercado_24h, acciones_del_dia, estado_mercado, tokens_*, idempotencia por (workspace, fecha))
- `docs/canonicas/eventos.md` · `briefing.published` refinado al payload real `{fecha, num_acciones, modelo_usado}` (legacy `briefing_id, date, top_actions_count, url_dashboard` marcado como propuesta inicial no implementada)
- `docs/knowledge/modelos_llm.md` · sección nueva "Uso actual de cada modelo (con caching)" documenta Build 1.1 (Haiku Scout) y Build 3.1 (Sonnet Strategist) con tamaño de prompt y razón de elección

## Errores cometidos y cómo se resolvieron

| Error | Causa raíz | Solución | Prevención futura |
| --- | --- | --- | --- |
| `KeyError: "Attempt to overwrite 'created' in LogRecord"` al hacer `logger.info(extra={"created": True, ...})` | Python logging tiene atributos reservados en `LogRecord` (created, name, levelname, msg, etc.) · pasar uno de esos en `extra` levanta `KeyError` antes de emitir el log | Renombrado `created` → `was_created` en el extra dict del Executive | Para cualquier `logger.info(extra=...)`, evitar keys: `name`, `msg`, `args`, `levelname`, `levelno`, `pathname`, `filename`, `module`, `exc_info`, `exc_text`, `stack_info`, `lineno`, `funcName`, `created`, `msecs`, `relativeCreated`, `thread`, `threadName`, `processName`, `process`. Documentado inline en el código del Executive. |

## Deuda técnica generada

- **Sin endpoint manual `POST /api/v1/briefing/trigger`** · cron es la única forma de generar briefing en Build 3.1. Si el job falla un día, el CEO no puede regenerar manualmente. Agregar en Build 3.2.
- **Sin retry en Anthropic API errors** · si la primera llamada falla (timeout, 503), el briefing del día queda degradado. No hay reintento automático. Aceptable para Build 3.1 · agregar exponential backoff con `tenacity` cuando empiece a doler.
- **`_parse_briefing_response` no valida que `acciones_del_dia` sea no-vacío.** Si el Strategist devuelve briefing válido con 0 acciones, se acepta. Esto es deliberado (días estables sin acción · el Strategist puede legítimamente devolver `[]`) · pero podría ocultar parser falla "silenciosa". Mitigación: el frontend muestra empty state visible "Sin acciones recomendadas hoy".
- **Cache hit rate no se mide.** Anthropic devuelve `cache_creation_input_tokens` y `cache_read_input_tokens` en `usage` · no los persisto. DT-008 implícita: en Build 5+ (Langfuse) capturar estos para validar que el cache realmente está pegando.

## Métricas de la fase

- Tests Build 3.1: 6 strategist + 2 executive + 2 briefing_api = 10 backend nuevos · 2 frontend
- Total acumulado: 118 backend + 23 frontend = 141/141 passing
- Lint: ruff check limpio (E501 ignorado en classifier+strategist por SYSTEM_PROMPT legible)
- Build frontend: 173 modules · 447 KB JS · sin warnings

## Cierre

### Build 3.1 · 2026-04-26
- Cerrado por: Andrés San Juan (CEO · approval pendiente) + Claude Code
- Rama: `phase-3/build-3.1-morning-briefing` → PR a `main`
- Próximo build: **3.2** — Recomendaciones de pricing con approval gate
