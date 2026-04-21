# CLAUDE.md · ARGOS

Reglas inamovibles del repositorio ARGOS de RODDOS S.A.S.
Este archivo es la fuente de verdad para Claude Code y todo desarrollador humano que trabaje sobre el repo.
Cualquier cambio aquí requiere PR explícito y aprobación del CEO.

Última actualización: Abril 2026 · Visión 2.0

---

## 1. Identidad del proyecto

- Nombre: ARGOS
- Propósito: cerebro de inteligencia comercial + frontend conversacional WhatsApp + motor de score crediticio para RODDOS S.A.S.
- Vertical primario: REPUESTOS para motos (negocio recurrente)
- Vertical secundario: VENTA DE MOTOS (puerta de entrada al cliente)
- Workspace inicial: RODDOS
- Multi-tenant: sí, desde día 1
- Stack: Python 3.11 + FastAPI + LangGraph + React 19 + TypeScript + MongoDB Atlas + Render
- Modelos LLM: Claude Sonnet 4.6 (default) · Haiku 4.5 (tareas simples) · Opus 4.7 (Strategist y casos críticos)

## 2. Principios arquitectónicos inamovibles

- Multi-tenant workspace_id en TODA colección y query, sin excepciones
- Bus argos_events append-only e inmutable
- Stateless agents, stateful bus
- Aislamiento de credenciales y blast radius respecto a SISMO V2 y respecto al admin de www.roddos.com
- Comunicación entre sistemas vía APIs autenticadas con keys dedicadas por dirección (lectura vs escritura)
- Toda acción que mueve dinero requiere approval humano explícito vía WhatsApp
- Score Engine es un clon interno de ARGOS, no una integración externa al motor de la web
- El motor de score vive en el admin web (www.roddos.com/admin) · ARGOS replica la lógica como clon independiente
- Loanbook de SISMO V2 NO contiene calificaciones del motor (todo ha sido manual hasta hoy) · lo que sí contiene es historial de cuotas pagadas/vencidas del cual se deriva un score_comportamental A+/A/B/C/D/E para habilitar Crédito Rodante directo a clientes recurrentes
- ARGOS lee read-only el historial de comportamiento de pago desde SISMO V2 para el bypass del flujo F3 (cliente RODDOS con historial positivo)

## 3. Reglas de Oro consolidadas (ROGs)

Todas las ROGs son inamovibles. Se imponen en código, no en prompt.
Cualquier prompt LLM que las contradiga se ignora.

### 3.1 ROGs originales de ARGOS (A1 a A12)

| ID | Regla |
|----|-------|
| ROG-A1 | Toda acción que mueve dinero requiere approval humano explícito |
| ROG-A2 | Spending caps validados por Compliance Officer en código, no en prompt |
| ROG-A3 | Multi-tenant workspace_id en TODA colección y query |
| ROG-A4 | Credenciales OAuth cifradas at-rest con KMS, nunca en plano |
| ROG-A5 | Verify before report (HTTP 200 confirmado en API externa) |
| ROG-A6 | Bus append-only — argos_events es inmutable |
| ROG-A7 | Stateless agents, stateful bus |
| ROG-A8 | Scraping respeta robots.txt + rate limits + proxies residenciales |
| ROG-A9 | Sin PII de terceros (sellers, usuarios) almacenada · solo agregados estadísticos |
| ROG-A10 | Compliance Officer puede vetar cualquier acción del Media Buyer |
| ROG-A11 | Aislamiento de credenciales y blast radius operativo respecto a SISMO V2 y al admin web · comunicación vía APIs autenticadas con keys dedicadas por dirección |
| ROG-A12 | Toda acción auditable en audit_log con quién/qué/cuándo |

### 3.2 ROGs del WhatsApp Agent (W1 a W8)

| ID | Regla |
|----|-------|
| ROG-W1 | Opt-in explícito antes de cualquier mensaje proactivo (utility o marketing) · sin opt-in registrado en SISMO + timestamp + canal de obtención no se envía nada |
| ROG-W2 | Negociación de descuentos limitada por margen mínimo definido en código · WhatsApp Agent nunca cierra venta por debajo del piso · si cliente lo pide escala al CEO |
| ROG-W3 | Stock se verifica en SISMO en tiempo real antes de confirmar venta · cero ventas de SKUs agotados |
| ROG-W4 | Handoff a humano obligatorio cuando cliente lo pide explícitamente · queja recurrente · monto > umbral · tema fuera del scope (garantías legales, devoluciones complejas) |
| ROG-W5 | Frecuencia máxima de mensajes proactivos: 1 cada 14 días por cliente, salvo respuesta directa a sus mensajes (ventana 24h) |
| ROG-W6 | AI chatbot debe tener tarea de negocio concreta (Meta 2026 enforcement) · cero conversaciones abiertas tipo "cómo estás" · cada conversación tiene goal medible |
| ROG-W7 | Cada conversación se etiqueta con resultado: vendió / no vendió / handoff humano / abandono |
| ROG-W8 | Datos de conversación nunca se usan para entrenar modelos de terceros · privacy by design · borrado por petición del cliente |

### 3.3 ROGs del Score Engine (S1 a S6)

| ID | Regla |
|----|-------|
| ROG-S1 | Score Engine es clon independiente del motor del admin de www.roddos.com · misma lógica, mismos pesos, mismos partners, instancia separada · cero llamadas cruzadas en runtime |
| ROG-S2 | Loanbook de SISMO V2 es fuente de verdad del historial de comportamiento de pago (cuotas pagadas, vencidas, días mora) · NO contiene scoring histórico · ARGOS lo consume read-only para derivar score_comportamental A+→E y habilitar bypass en flujo F3 |
| ROG-S3 | Reglas duras de rechazo se ejecutan ANTES del cálculo del score, no después · si AUCO < 70 o RiskSeal flag fraude o mora > $3M, no se llama a Claude ni se calcula score |
| ROG-S4 | Decisión crediticia siempre auditable · narrativa generada por Claude se persiste en scoring_solicitudes con timestamp y versión del prompt |
| ROG-S5 | Versiones del XGBoost pineadas con joblib + hash · cada deploy del modelo registra hash del modelo activo en argos_events |
| ROG-S6 | Notificación de decisión solo por WhatsApp vía Mercately · email queda excluido en ARGOS por decisión del CEO (el motor de la web sí notifica por email) |

## 4. Estructura de carpetas

```
ARGOS/
├── CLAUDE.md                    ← este archivo, raíz del repo
├── docs/
│   ├── canonicas/               ← rutas, eventos, integraciones (mapas de conexión)
│   │   ├── README.md
│   │   ├── eventos.md
│   │   ├── apis_internas.md
│   │   ├── apis_externas.md
│   │   ├── colecciones_mongo.md
│   │   ├── integraciones_sismo.md
│   │   └── flujos_negocio.md
│   ├── claude/                  ← bitácora arquitectónica por fase
│   │   ├── README.md
│   │   ├── phase_0_bootstrap.md
│   │   ├── phase_1_marketplace.md
│   │   ├── ... (una por fase)
│   │   └── errores_recurrentes.md
│   └── knowledge/               ← skills, configs, partners
│       ├── README.md
│       ├── agents/              ← config de los 11 agentes
│       │   ├── scout.md
│       │   ├── marketplace.md
│       │   ├── trends.md
│       │   ├── competitors.md
│       │   ├── social.md
│       │   ├── strategist.md
│       │   ├── executive.md
│       │   ├── media_buyer.md
│       │   ├── compliance_officer.md
│       │   ├── whatsapp_agent.md
│       │   └── score_engine.md
│       ├── skills/              ← prompts y templates reusables
│       ├── stack.md
│       ├── modelos_llm.md
│       └── partners.md
├── .planning/                   ← prompts secuenciales para Claude Code
│   ├── phase_0_prompt.md
│   ├── phase_1_prompt.md
│   └── ...
├── src/
├── tests/
└── ...
```

## 5. Convenciones de código

### 5.1 Naming

- Python: snake_case · módulos en lowercase · clases en PascalCase
- TypeScript: camelCase · componentes React en PascalCase
- MongoDB collections: snake_case plural (workspaces, scoring_solicitudes, conversaciones)
- Eventos del bus: dot.notation jerárquico (score.evaluated, payment.received, conversation.opened)
- API endpoints: kebab-case · /api/scoring/solicitar · /api/whatsapp/webhook
- Variables de entorno: SCREAMING_SNAKE_CASE

### 5.2 Commits

Formato Conventional Commits con scope obligatorio:

```
<type>(<scope>): <subject>

[body opcional con detalle del qué y por qué]

Refs: phase_X / build_Y / canónica afectada
```

Tipos permitidos: feat, fix, refactor, docs, test, chore, perf, ci, build
Scopes válidos: scoring, whatsapp, marketplace, trends, competitors, social, strategist, executive, media_buyer, compliance, scout, infra, docs, sismo, partner

Cada commit que toque una integración debe actualizar la canónica correspondiente en el mismo PR.
Cada PR que cierre un build debe actualizar la bitácora docs/claude/phase_X.md en el mismo PR.

### 5.3 Tests

- TDD obligatorio en módulos críticos: Score Engine, Compliance Officer, Media Buyer, Wava integration
- Cobertura mínima 80% en estos módulos
- Smoke tests obligatorios al cierre de cada build
- Tests de integración con mocks para todos los partners externos

## 6. Política de partners externos

| Partner | Función | Criticidad | Modo |
|---------|---------|------------|------|
| Mercately | BSP de WhatsApp | Crítica | Producción · usa instancia ya integrada en SISMO Build 14 |
| Wava | Pasarela Nequi/Daviplata para inicial y cuotas | Crítica | Nueva integración · API a la medida |
| RiskSeal | Antifraude digital footprint primario para repuestos | Crítica | Nueva integración · API REST |
| AUCO | Biometría + validación documento | Crítica | Producción · ya en uso en onboarding |
| Palenca | Ingresos verificados delivery/mototaxi | Alta | Replicar integración existente del admin web |
| Datacrédito | Historial crediticio bancario tradicional | Media | Manual · solo se consulta en revisión manual del analista, no automatizable vía API |
| MELI API | Marketplace inteligencia repuestos | Alta | OAuth · ya documentado |
| Meta Marketing API | Pauta digital | Alta | System User ARGOS dedicado dentro de BM existente RODDOS · preserva histórico |
| Google Ads API | Pauta digital | Alta | Service Account ARGOS dedicado dentro de MCC existente RODDOS · preserva histórico |
| Apify | Scraping FB Marketplace + FB Ads | Alta | Tier starter |
| TikHub.io | Social listening IG + TikTok | Media | Tier básico |
| SerpAPI | Google Trends + transparencia ads | Media | 5K queries/mes |
| Anthropic | LLMs Sonnet 4.6 + Haiku 4.5 + Opus 4.7 | Crítica | Prompt caching activo |

## 7. Política de errores y deuda técnica

- Cada error en producción que cueste >30 min de debug se registra en docs/claude/errores_recurrentes.md
- Cada deuda técnica conocida pero no resuelta se registra en collection deuda_tecnica con prioridad y owner
- Cada vez que se descubre una decisión arquitectónica que contradiga este CLAUDE.md, se abre PR de corrección antes de seguir desarrollando

## 8. Roles y workflow

| Rol | Quién | Responsabilidad |
|-----|-------|-----------------|
| Arquitecto / configurador | Claude.ai | Specs, prompts, canónicas, knowledge, audits, diagnósticos |
| Constructor | Claude Code | Código, commits, tests, terminal, deployment |
| CEO / decisor | Andrés | Aprobaciones de fase, decisiones de producto, approvals de pauta y crédito |
| QA | Claude Code + smoke tests | TDD obligatorio en módulos críticos |

Interfaz Claude.ai → Claude Code: archivos `.planning/phase_X_prompt.md` en el repo.
Cada nuevo build empieza leyendo este CLAUDE.md + canónica relevante + bitácora de la fase actual.

## 9. Lo que ARGOS NO es

- No es un CRM (eso es HubSpot)
- No es un ERP completo (eso es SISMO V2)
- No es un sistema contable
- No es un sistema de cobranza puro (eso es RADAR dentro de SISMO V2 · ARGOS dispara pero no procesa)
- No es una herramienta de creatividad (no genera diseños)
- No es un proveedor de tráfico (optimiza pauta, no garantiza resultados)
- No es un reemplazo del motor de score del admin web · es un clon independiente para WhatsApp
