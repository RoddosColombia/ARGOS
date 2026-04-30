# CLAUDE.md · ARGOS

Reglas inamovibles del repositorio ARGOS de RODDOS S.A.S.
Este archivo es la fuente de verdad para Claude Code y todo desarrollador humano que trabaje sobre el repo.
Cualquier cambio aquí requiere PR explícito y aprobación del CEO.

Última actualización: Abril 2026 · Visión 2.1
Cambios principales vs versión anterior: ROGs S1/S3/S4/S5/S6 reescritas (Score Engine pass-through), nueva categoría ROG-G (Governance multi-role), sección 8 con CGO como rol nativo, sección 9 con cobranza fuera de scope. Justificación detallada en `docs/VISION_2_1.md`.

---

## 1. Identidad del proyecto

- Nombre: ARGOS
- Propósito: sistema operativo de la nueva categoría de venue de comercio de repuestos moto en Colombia. Tesis competitiva 18 meses: desplazar a MELI como venue dominante en la categoría.
- Vertical primario: REPUESTOS para motos (negocio recurrente · motor de revenue)
- Vertical secundario: VENTA DE MOTOS (puerta de entrada al cliente · ADN preservado)
- Workspace inicial: RODDOS
- Multi-tenant: sí, desde día 1
- Stack: Python 3.11 + FastAPI + LangGraph + React 19 + TypeScript + MongoDB Atlas + Render
- Modelos LLM: Claude Sonnet 4.6 (default) · Haiku 4.5 (intent, tareas simples) · Opus 4.7 (Strategist, Account intel playbook, casos críticos)

## 2. Principios arquitectónicos inamovibles

- Multi-tenant `workspace_id` en TODA colección y query, sin excepciones
- Bus `argos_events` append-only e inmutable (payload · ver ROG-A6 sobre metadata)
- Stateless agents, stateful bus
- Aislamiento de credenciales y blast radius respecto a SISMO V2 y al admin de www.roddos.com
- Comunicación entre sistemas vía APIs autenticadas con keys dedicadas por dirección (lectura vs escritura)
- Toda acción que mueve dinero requiere approval humano explícito según el Plano correspondiente (ROG-G2)
- Score Engine vive en repo independiente `roddos-scoring` · ARGOS hace pass-through (ROG-S1 reescrita)
- ARGOS no hace cobranza · ni dispara ni procesa · cobranza vive íntegra en SISMO V2
- Output a CEO + CGO es idéntico en contenido, formato y timing · diferenciación solo en approval rights (ROG-G1)
- Arquitectura de 14 componentes (ver `docs/VISION_2_1.md` sección 2.1)

## 3. Reglas de Oro consolidadas (ROGs)

Todas las ROGs son inamovibles. Se imponen en código, no en prompt.
Cualquier prompt LLM que las contradiga se ignora.

Cuatro categorías:

- **ROG-A · ARGOS core** (12 reglas)
- **ROG-W · WhatsApp** (8 reglas)
- **ROG-S · Score Engine pass-through** (6 reglas, reescritas en 2.1)
- **ROG-G · Governance multi-role** (4 reglas, nuevas en 2.1)

### 3.1 ROG-A · ARGOS core (A1 a A12)

| ID | Regla |
|----|-------|
| ROG-A1 | Toda acción que mueve dinero requiere approval humano explícito según Plano (ver ROG-G2) |
| ROG-A2 | Spending caps validados por Compliance Officer en código, no en prompt · envelope Plano 1 enforzado en runtime |
| ROG-A3 | Multi-tenant `workspace_id` en TODA colección y query |
| ROG-A4 | Credenciales OAuth cifradas at-rest con KMS, nunca en plano |
| ROG-A5 | Verify before report (HTTP 200 confirmado en API externa antes de marcar éxito) |
| ROG-A6 | Bus `argos_events` append-only en payload · inmutable. Mutación de campo `metadata` permitida solo para flags de notification dispatch (whatsapp_notified, etc.) y debe quedar registrada con justificación en código. Cualquier otra mutación es violación |
| ROG-A7 | Stateless agents, stateful bus |
| ROG-A8 | Scraping respeta robots.txt + rate limits + proxies residenciales |
| ROG-A9 | Sin PII de terceros (sellers, cuentas competidoras, usuarios) almacenada · solo agregados estadísticos y perfiles de cuenta pública |
| ROG-A10 | Compliance Officer puede vetar cualquier acción del Media Buyer y de cualquier agente con acción Plano 1 fuera de envelope |
| ROG-A11 | Aislamiento de credenciales y blast radius operativo respecto a SISMO V2 y al admin web · comunicación vía APIs autenticadas con keys dedicadas por dirección |
| ROG-A12 | Toda acción auditable en `audit_log` con quién (role + user_id) / qué / cuándo / contexto · enforced en código, no opcional |

### 3.2 ROG-W · WhatsApp (W1 a W8)

| ID | Regla |
|----|-------|
| ROG-W1 | Opt-in explícito antes de cualquier mensaje proactivo (utility o marketing) · sin opt-in registrado en collection `contacts` con timestamp + canal de obtención no se envía nada · enforced en código |
| ROG-W2 | Negociación de descuentos limitada por margen mínimo definido en código · WhatsApp Agent nunca cierra venta por debajo del piso · si cliente lo pide escala a Plano 3 (CEO) |
| ROG-W3 | Stock se verifica en SISMO en tiempo real antes de confirmar venta · cero ventas de SKUs agotados |
| ROG-W4 | Handoff a humano obligatorio cuando cliente lo pide explícitamente · queja recurrente · monto > umbral · tema fuera del scope (garantías legales, devoluciones complejas) |
| ROG-W5 | Frecuencia máxima de mensajes proactivos: 1 cada 14 días por cliente, salvo respuesta directa a sus mensajes (ventana 24h) · Compliance Officer enforza |
| ROG-W6 | AI chatbot debe tener tarea de negocio concreta (Meta 2026 enforcement) · cero conversaciones abiertas tipo "cómo estás" · cada conversación tiene goal medible |
| ROG-W7 | Cada conversación se etiqueta con outcome: vendió / no vendió / handoff humano / abandono · obligatorio · sin outcome la conversación queda en queue de revisión |
| ROG-W8 | Datos de conversación nunca se usan para entrenar modelos de terceros · privacy by design · borrado por petición del cliente |

### 3.3 ROG-S · Score Engine pass-through (S1 a S6, reescritas en 2.1)

Cambio fundamental vs versión 2.0: el Score Engine **NO** es clon dentro de ARGOS. Vive en repo independiente `https://github.com/RoddosColombia/roddos-scoring` operado por Iván Echeverri (CGO). ARGOS hace pass-through HTTP. Razón: governance crediticia única (ver `docs/VISION_2_1.md` sección 3.2).

| ID | Regla |
|----|-------|
| ROG-S1 | ARGOS es pass-through al motor de `roddos-scoring`. NO ejecuta lógica crediticia, NO aplica reglas duras, NO llama Claude para narrativa crediticia. La governance crediticia (pesos XGBoost, integraciones nuevas, reglas duras, auditoría regulatoria) vive en `roddos-scoring` bajo ownership del CGO |
| ROG-S2 | Loanbook SISMO V2 es fuente de verdad del historial de comportamiento de pago · ARGOS lo lee read-only para derivar `score_comportamental` A+/A/B/C/D/E que habilita bypass del flujo F3 (cliente RODDOS con historial positivo) |
| ROG-S3 | Política de degradación: si `roddos-scoring` está caído, ARGOS pausa nuevas aprobaciones de crédito (no aprueba sin score) pero sigue procesando ventas cash, F4 cash, consultas de stock, cotizaciones, briefs y recomendaciones |
| ROG-S4 | ARGOS persiste audit local en `audit_log` de cada llamada a `/v1/evaluate`: timestamp, workspace_id, actor (role + user), payload enviado (sin PII directa), decision recibida, engine_version. Cumple ROG-A12 lado-Argos |
| ROG-S5 | Contrato API canónico vive en `docs/canonicas/score_engine_contract.md` con schema JSON versionado · 1 test de contrato corriendo en CI semanal valida que el response sigue cumpliendo el schema · si falla, se notifica antes de que rompa producción |
| ROG-S6 | Notificación de decisión crediticia solo por WhatsApp vía Mercately · email queda excluido en ARGOS por decisión del CEO (el motor del admin web sí notifica por email; la diferencia es operativa, no técnica) |

### 3.4 ROG-G · Governance multi-role (G1 a G4, nuevas en 2.1)

| ID | Regla |
|----|-------|
| ROG-G1 | Output unificado CEO + CGO. Todos los reportes, briefs, dashboards y notificaciones se entregan **simultáneamente, mismo formato, mismo contenido** a CEO (Andrés San Juan) y CGO (Iván Echeverri). No hay versión cliente-side ni delegación de información. Diferenciación solo en cola de approvals según role |
| ROG-G2 | Tres planos de approval enforzados en código por Compliance Officer: Plano 1 reversibles dentro de envelope (auto-ejecutado por ARGOS, log al cierre del día); Plano 2 tácticas con costo material (CGO aprueba, default rechazo en 24h con notificación a CEO); Plano 3 estratégicas (CEO aprueba). Mapeo en cada `recommendation` vía campo `approval_required_role` |
| ROG-G3 | `audit_log` registra qué role (CEO o CGO o sistema) aprobó qué acción · accountability mutua sin opacidad · CEO y CGO pueden auditar la cola del otro |
| ROG-G4 | Envelope del Plano 1 (rangos permitidos en pricing, bidding, pausa de ad sets, etc.) se define en colección `compliance_envelope` con timestamp y aprobación CEO. Cambios al envelope requieren PR explícito y review CEO |

## 4. Estructura de carpetas

```
ARGOS/
├── CLAUDE.md                    ← este archivo, raíz del repo
├── docs/
│   ├── VISION_2_0.md            ← histórico (preservar como referencia)
│   ├── VISION_2_1.md            ← documento ejecutivo maestro vigente
│   ├── canonicas/               ← rutas, eventos, integraciones (mapas de conexión)
│   │   ├── README.md
│   │   ├── eventos.md
│   │   ├── apis_internas.md
│   │   ├── apis_externas.md
│   │   ├── colecciones_mongo.md
│   │   ├── integraciones_sismo.md   ← incluye 4 endpoints write ARGOS → SISMO desde Capa 0
│   │   ├── score_engine_contract.md ← nuevo en Capa 0 · schema JSON versionado del Score Engine
│   │   └── flujos_negocio.md
│   ├── claude/                  ← bitácora arquitectónica por fase
│   │   ├── README.md
│   │   ├── phase_0_bootstrap.md
│   │   ├── phase_1_marketplace.md
│   │   ├── phase_2_score_engine.md
│   │   ├── phase_2.5_alineacion.md  ← nuevo en Capa 0
│   │   ├── ... (una por fase)
│   │   └── errores_recurrentes.md
│   └── knowledge/               ← skills, configs, agents, partners
│       ├── README.md
│       ├── agents/              ← config de los 14 agentes
│       │   ├── scout.md
│       │   ├── marketplace.md
│       │   ├── trends.md
│       │   ├── competitors.md
│       │   ├── social.md
│       │   ├── sku_canonicalizer.md     ← nuevo en 2.1
│       │   ├── portfolio.md             ← nuevo en 2.1
│       │   ├── account_intel.md         ← nuevo en 2.1
│       │   ├── strategist.md
│       │   ├── pricing_engine.md        ← nuevo en 2.1 (antes implícito en strategist)
│       │   ├── media_buyer.md
│       │   ├── compliance_officer.md
│       │   ├── whatsapp_agent.md
│       │   └── executive.md
│       ├── skills/              ← prompts y templates reusables
│       ├── stack.md
│       ├── modelos_llm.md
│       └── partners.md
├── .planning/                   ← prompts secuenciales para Claude Code
│   ├── phase_0_prompt.md
│   ├── phase_2.5_prompt.md      ← nuevo en Capa 0
│   ├── phase_3_prompt.md        ← se redacta al cerrar Capa 0
│   └── ...
├── src/
├── tests/
└── ...
```

## 5. Convenciones de código

### 5.1 Naming

- Python: snake_case · módulos en lowercase · clases en PascalCase
- TypeScript: camelCase · componentes React en PascalCase
- MongoDB collections: snake_case plural (workspaces, scoring_solicitudes, conversaciones, contacts, compliance_envelope)
- Eventos del bus: dot.notation jerárquico (`score.evaluated`, `payment.received`, `conversation.opened`, `competitor.meli.price_change`, `inventory.stockout.predicted`)
- API endpoints: kebab-case · `/api/v1/scoring/solicitar` · `/api/v1/whatsapp/webhook` · `/api/v1/contacts/{id}/opt-in`
- Variables de entorno: SCREAMING_SNAKE_CASE

### 5.2 Commits

Formato Conventional Commits con scope obligatorio:

```
<type>(<scope>): <subject>

[body opcional con detalle del qué y por qué]

Refs: phase_X / build_Y / canónica afectada
```

Tipos permitidos: feat, fix, refactor, docs, test, chore, perf, ci, build
Scopes válidos: scoring, whatsapp, marketplace, trends, competitors, social, strategist, executive, media_buyer, compliance, scout, infra, docs, sismo, partner, sku_canon, portfolio, account_intel, pricing

Cada commit que toque una integración debe actualizar la canónica correspondiente en el mismo PR.
Cada PR que cierre un build debe actualizar la bitácora `docs/claude/phase_X.md` en el mismo PR.

### 5.3 Tests

- TDD obligatorio en módulos críticos: Score Engine pass-through, Compliance Officer, Media Buyer, Wava integration, audit_log writers, opt-in registry, SISMO write
- Cobertura mínima 80% en estos módulos · enforced en CI con `pytest-cov --cov-fail-under=80`
- Smoke tests obligatorios al cierre de cada build
- Tests de integración con mocks para todos los partners externos (httpx.MockTransport recomendado)
- Test de contrato Score Engine corre weekly en CI (ROG-S5)

### 5.4 CI como gate de merge (no negociable)

**Ningún PR se mergea con checks de CI en rojo.** Aplica a todos los workflows del repo (hoy: `Backend · ruff + pytest + cov` y `Frontend · tsc + vitest + vite build` y `Score Engine · contract test weekly`).

- Si un check falla, la rama se arregla primero · force-push al mismo branch si es necesario · esperar CI verde · entonces mergear.
- Excepciones requieren autorización escrita del CEO en el PR y se registran en `docs/claude/errores_recurrentes.md`.
- Flakes conocidos se ignoran solo tras documentarlos en `docs/claude/deuda_tecnica.md` con ETA de fix.
- Branch protection en `main` enforza la regla a nivel GitHub · no depender del honor system.
- Agentes (Claude Code incluido) no mergean PRs con CI rojo aunque el humano lo pida sin justificación escrita.

## 6. Política de partners externos

| Partner | Función | Criticidad | Modo |
|---------|---------|------------|------|
| Mercately | BSP de WhatsApp | Crítica | Producción · usa instancia ya integrada en SISMO Build 14 (confirmar reuso WABA o WABA dedicada para ARGOS antes de Capa 1) |
| Wava | Pasarela Nequi/Daviplata para inicial y cuotas | Crítica | Nueva integración · API a la medida · onboarding 2-3 semanas · arrancar antes de Capa 1 |
| `roddos-scoring` | Motor de score crediticio (repo Iván) | Crítica | Pass-through HTTP · contrato versionado en `docs/canonicas/score_engine_contract.md` |
| RiskSeal | Antifraude digital footprint primario para repuestos | Crítica | Nueva integración · API REST · invocada desde `roddos-scoring` (ARGOS no llama directo) |
| AUCO | Biometría + validación documento | Crítica | Producción · ya en uso en onboarding · invocada desde `roddos-scoring` |
| Palenca | Ingresos verificados delivery/mototaxi | Alta | Replicar integración existente · invocada desde `roddos-scoring` |
| Datacrédito | Historial crediticio bancario tradicional | Media | Manual · solo se consulta en revisión manual del analista, no automatizable vía API |
| MELI API | Marketplace inteligencia repuestos + write para listings (en Capa 5) | Crítica | OAuth · ya documentado |
| Meta Marketing API | Pauta digital + Ad Library | Alta | System User ARGOS dedicado dentro de BM existente RODDOS · preserva histórico |
| Google Ads API | Pauta digital | Alta | Service Account ARGOS dedicado dentro de MCC existente RODDOS · preserva histórico |
| Apify | Scraping FB Marketplace + FB Ads + competidores top 20 + IG | Alta | Tier starter |
| TikHub.io | Social listening IG + TikTok + tracking de cuentas específicas | Media | Tier básico |
| SerpAPI | Google Trends + transparencia ads + Google Shopping | Media | 5K queries/mes |
| Anthropic | LLMs Sonnet 4.6 + Haiku 4.5 + Opus 4.7 | Crítica | Prompt caching activo |
| Langfuse | Observabilidad LLM (costos, latencias, traces) | Alta | Self-hosted en Render · pendiente Capa 0 |

## 7. Política de errores y deuda técnica

- Cada error en producción que cueste >30 min de debug se registra en `docs/claude/errores_recurrentes.md`
- Cada deuda técnica conocida pero no resuelta se registra en `docs/claude/deuda_tecnica.md` con prioridad y owner
- Cada vez que se descubre una decisión arquitectónica que contradiga este CLAUDE.md, se abre PR de corrección antes de seguir desarrollando
- Hallazgos de auditoría externa (auditorías post-fase, revisiones del CEO) se incorporan vía PR explícito al CLAUDE.md · una sola fuente de verdad

## 8. Roles y workflow

| Rol | Quién | Responsabilidad | Approval rights |
|-----|-------|-----------------|-----------------|
| Arquitecto / configurador | Claude.ai | Specs, prompts, canónicas, knowledge, audits, diagnósticos | N/A |
| Constructor | Claude Code | Código, commits, tests, terminal, deployment | N/A |
| CEO | Andrés San Juan | Decisiones de producto, estructura, sourcing, partners, margen piso, spending caps mensuales totales | Plano 3 + revisión Plano 2 si CGO no aprueba en 24h |
| CGO | Iván Echeverri | Ejecución de campañas, pauta digital, creative, audiencias, promo calendar, pricing táctico | Plano 2 |
| Sistema (ARGOS) | Compliance Officer + agentes | Acciones reversibles dentro de envelope predefinido | Plano 1 (auto-ejecución) |
| QA | Claude Code + smoke tests | TDD obligatorio en módulos críticos | N/A |

Interfaz Claude.ai → Claude Code: archivos `.planning/phase_X_prompt.md` en el repo.
Cada nuevo build empieza leyendo este CLAUDE.md + `docs/VISION_2_1.md` + canónica relevante + bitácora de la fase actual.

CEO y CGO comparten visibilidad total de información (ROG-G1) y de approvals (ROG-G3). Cada uno opera en su scope de approval pero ambos ven el mismo brief, mismo dashboard, mismas alertas, simultáneamente.

## 9. Lo que ARGOS NO es

- No es un CRM (eso es HubSpot)
- No es un ERP completo (eso es SISMO V2)
- No es un sistema contable
- **No es un sistema de cobranza · ni dispara ni procesa · cobranza recurrente vive íntegra en SISMO V2** (corrección 2.1 · cambio respecto a Visión 2.0 sección 4.7 que asumía F5 dentro de ARGOS)
- No es una herramienta de creatividad (no genera diseños ni copy de campañas; sí sugiere qué SKUs amplificar y produce briefs creative-direction para alimentar al equipo de contenido humano)
- No es un proveedor de tráfico (optimiza pauta, no garantiza resultados)
- No es un reemplazo del Score Engine · es pass-through HTTP vía API del repo `roddos-scoring`
- No es un sistema de governance unilateral · CEO y CGO son co-recipientes de información idéntica con scope de approval diferenciado (ROG-G1, ROG-G2)

## 10. Cambios principales 2.0 → 2.1 (resumen para auditoría)

- Sección 1: tesis competitiva 18 meses contra MELI explicitada
- Sección 2: arquitectura de 14 componentes (3 nuevos: SKU canonicalizer, Portfolio agent, Account intel) · principios actualizados con multi-role y cobranza fuera de scope
- Sección 3: ROGs S1/S3/S4/S5/S6 reescritas (Score Engine pass-through, no clon) + nueva categoría ROG-G con 4 reglas de governance multi-role
- Sección 4: estructura de carpetas con archivos nuevos (`VISION_2_1.md`, `score_engine_contract.md`, `phase_2.5_alineacion.md`, agentes nuevos en `knowledge/agents/`)
- Sección 5: scopes de commit ampliados (sku_canon, portfolio, account_intel, pricing) · CI con coverage enforced
- Sección 6: tabla de partners actualizada con `roddos-scoring`, RiskSeal/AUCO/Palenca como invocados por el motor externo, Langfuse como pendiente Capa 0
- Sección 8: CGO como rol nativo con Plano 2 · CEO y CGO comparten información (ROG-G1)
- Sección 9: cobranza explícitamente fuera de scope · ARGOS no genera creatividad pero sí sugiere
