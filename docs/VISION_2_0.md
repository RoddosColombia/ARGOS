# ARGOS — Visión 2.0

> **Documento ejecutivo maestro.** Fuente de verdad del proyecto.
> Fuente original: `ARGOS_VISION_2.0.docx` en la raíz del repo.
> Última actualización: Abril 2026 · Versión 2.0

---

ARGOS
Visión 2.0
Tienda super poderosa en WhatsApp + Inteligencia de Mercado + Score Engine clonado
Foco recurrente: REPUESTOS · Puerta de entrada: MOTOS
RODDOS S.A.S.
Bogotá, Colombia · Abril 2026
Documento ejecutivo · Arquitectura + Flujos + Plan de trabajo v5

# 0. Resumen ejecutivo
ARGOS Visión 2.0 consolida tres sistemas bajo un solo cerebro: un canal comercial conversacional vía WhatsApp que acelera ventas de repuestos día a día, un motor de inteligencia de mercado con 9 agentes especializados que decide qué pautar y qué recomendar, y un motor de calificación crediticia clonado independiente del que vive en el admin de www.roddos.com.
El corazón del negocio son los REPUESTOS. La moto es la puerta de entrada al cliente; los repuestos son el ingreso recurrente de 5+ años. Un cliente que compra moto consume aceite cada 4-5 semanas, filtros cada 6-12 semanas, pastillas cada 6-12 semanas, cadena cada 8-10 meses, llantas cada 10-12. Mototaxistas y deliverys (el 70% del segmento RODDOS) tienen un uso 2x-2.5x más intensivo. Cada venta de repuesto con Crédito Rodante tiene aprobación casi automática para clientes con historial positivo (bypass con umbral 400 vs 500 normal · ROG-S1). Esa es la máquina de revenue recurrente.
El documento cubre: tesis comercial (sección 1), arquitectura de 11 componentes (sección 2), Score Engine clonado (sección 3), los 6 flujos de negocio (sección 4), plan de trabajo v5 de 10 fases (sección 5), metodología de trabajo con 3 carpetas (sección 6), presupuesto y riesgos (sección 7), y checklist de decisiones pendientes (sección 8).
El paquete de archivos .md que acompaña este documento implementa la metodología de SISMO V2: carpetas canonicas/, claude/, knowledge/ + CLAUDE.md raíz + .planning/. Se entrega listo para arrastrar al Desktop y apuntar Claude Code al directorio para iniciar Phase 0.
## Recomendación
PROCEDER a Phase 0. El sistema de score ya existe (Build 20 del admin web · se replica como clon · ROG-S1). WhatsApp ya está integrado vía Mercately (Build 14 del admin web · se reusa la WABA). Wava y RiskSeal son integraciones nuevas, pero bien documentadas y con APIs maduras. El loop F3 ↔ F6 (venta de repuesto a cliente RODDOS + re-compra proactiva por mantenimiento predictivo) es el motor del negocio. Una vez operativo, cada cliente moto se convierte en 20+ ventas de repuestos durante su vida útil con RODDOS.

# 1. Tesis comercial recentrada
## 1.1 La máquina de revenue recurrente
RODDOS no es un negocio de vender motos. Es un negocio de adquirir clientes con la moto, y monetizarlos con repuestos durante los siguientes 5 años.
La matemática:
1 TVS Raider 125 vendida hoy = 1 cliente adquirido
Cada cliente consume entre 6 y 12 repuestos/año · ticket promedio $15K-$80K COP
LTV conservador a 5 años: $1.2M-$2.5M COP en repuestos
Margen de repuestos es históricamente mayor que el de motos nuevas
Un mototaxista o delivery (40% del cliente RODDOS) consume 1.5x-2x más
ARGOS convierte esa promesa en sistema: WhatsApp como canal recurrente de contacto, motor de mantenimiento predictivo que anticipa la necesidad antes que el cliente pregunte, Crédito Rodante con bypass para clientes con historial A+/A/B (aprobación casi automática con umbral 400), y cobranza por Nequi/Daviplata que mantiene la salud financiera sin fricciones.
## 1.2 Por qué ahora
Costo LLMs cayó 70% en 18 meses (Sonnet 4.6 · Haiku 4.5 · Opus 4.7). Razonamiento agéntico es rentable.
MCP estándar adoptado por Anthropic, OpenAI, Microsoft, Google. Herramientas se integran nativamente.
WhatsApp en Colombia: 74% de empresas ya venden por ahí con tasas de conversión 13-19x vs ecommerce tradicional.
Wava es Partner oficial de Nequi y Daviplata (30M+ usuarios) · partner ideal para el segmento RODDOS.
RiskSeal resuelve el hueco de Datacrédito-sin-API con digital footprint antifraude (98% cobertura en población underserved).
La ventana está abierta HOY. En 18 meses el espacio estará saturado (Cances/Serpion en Bogotá ya está construyendo algo conceptualmente análogo).
## 1.3 Diferenciación defendible
Ningún competidor integra OBSERVAR + ENTENDER + DECIDIR + EJECUTAR en un solo agente IA con foco vertical. Existen 10+ plataformas que cubren 1 o 2 de esos pilares (BigSpy, AdSpy, Minea, Browse AI, Triple Whale, Pacvue, Lindy, Hootsuite). Ninguna combina los 4 en LATAM con enfoque vertical en repuestos motos + integración con loanbook propio + WhatsApp commerce + Score Engine interno.

# 2. Arquitectura de 11 componentes
ARGOS está construido como un sistema multi-agente con un bus de eventos append-only (argos_events) como único medio de comunicación entre agentes. Cada agente es stateless; el estado vive en el bus (ROG-A7). Esto permite reemplazar agentes sin perder historia.
## 2.1 Los 11 componentes

| Componente | Nivel | Dominio | Modelo LLM |
| --- | --- | --- | --- |
| Scout | N0 | Descubrimiento amplio · primer filtro de señales | Haiku 4.5 |
| Marketplace Agent | N1 | MELI + FB Marketplace · repuestos 80% · motos 20% | Sonnet 4.6 |
| Trends Agent | N1 | Google Trends + SerpAPI · keywords en spike | Sonnet 4.6 |
| Competitors Agent | N1 | Meta Ad Library comercial + Google Transparency | Sonnet 4.6 / Opus 4.7 |
| Social Agent | N1 | IG + TikTok + YouTube Shorts vía TikHub.io | Sonnet 4.6 vision |
| Strategist | N2 | Síntesis + recomendaciones + briefing + mantenimiento F6 | Opus 4.7 + Sonnet 4.6 |
| Executive | N2 | Interfaz con CEO · briefing diario · approval gates | Sonnet 4.6 |
| Media Buyer | N3 | Ejecución pauta Meta + Google + CTW ads | Sonnet 4.6 |
| Compliance Officer | N2 | Guardrail en código de spending caps, opt-in, margen | Sonnet 4.6 (casos ambiguos) |
| WhatsApp Agent | N1 | Frontend conversacional · KYC · venta · cobro · soporte | Sonnet 4.6 multimodal |
| Score Engine | N3 | Motor de calificación crediticia · clon del admin web | Sonnet 4.6 (Capa 2) |

## 2.2 Capas del sistema

| Capa | Contenido |
| --- | --- |
| 7 — EXPERIENCIA | WhatsApp (cliente final) · Web interna /briefing (CEO+analista) · Webhooks outbound |
| 6 — AGENTES | LangGraph supervisor · los 11 agentes coordinados |
| 5 — RAZONAMIENTO Y MEMORIA | Claude Sonnet 4.6 + Haiku 4.5 + Opus 4.7 · GraphRAG por workspace · memoria corto plazo (sesión) + largo plazo (aprendizajes) |
| 4 — TOOLS Y SCRAPING | Scrapling + Crawl4AI · Apify (FB MP + Ad Library) · ProxyRack residenciales |
| 3 — INTEGRACIONES OFICIALES | MELI · Meta Ads · Google Ads · Mercately · Wava · RiskSeal · AUCO · Palenca · TikHub · SerpAPI · Anthropic |
| 2 — DATOS Y BUS | MongoDB Atlas + backups nativos · Qdrant vectores · Redis cola · Render Persistent Disk · argos_events append-only |
| 1 — INFRAESTRUCTURA | Render (backend + frontend) · Docker · GitHub Actions CI/CD · argos.roddos.com vía CNAME GoDaddy |

## 2.3 Las 3 Reglas de Oro por dominio
Las ROGs son inamovibles. Se imponen en código, no en prompt. El CLAUDE.md raíz del repo las consagra en la sección 3.
### ROG-A (ARGOS core · 12 reglas)
ROG-A1 Toda acción que mueve dinero requiere approval humano explícito
ROG-A2 Spending caps validados por Compliance en código, no en prompt
ROG-A3 Multi-tenant workspace_id en TODA colección y query
ROG-A4 Credenciales OAuth cifradas at-rest con KMS
ROG-A5 Verify before report (HTTP 200 confirmado en API externa)
ROG-A6 Bus append-only · argos_events es inmutable
ROG-A7 Stateless agents, stateful bus
ROG-A8 Scraping respeta robots.txt + rate limits + proxies residenciales
ROG-A9 Sin PII de terceros · solo agregados estadísticos
ROG-A10 Compliance Officer puede vetar cualquier acción del Media Buyer
ROG-A11 Aislamiento de credenciales y blast radius respecto a SISMO V2 y al admin web · comunicación vía APIs autenticadas
ROG-A12 Toda acción auditable en audit_log con quién/qué/cuándo

### ROG-W (WhatsApp · 8 reglas)
ROG-W1 Opt-in explícito antes de cualquier mensaje proactivo
ROG-W2 Negociación con piso de margen validado en código
ROG-W3 Stock verificado en SISMO en tiempo real antes de confirmar venta
ROG-W4 Handoff a humano cuando cliente lo pide o es tema fuera de scope
ROG-W5 Frecuencia máxima 1 mensaje proactivo cada 14 días por cliente
ROG-W6 AI chatbot con tarea de negocio concreta · cero conversaciones abiertas (Meta 2026)
ROG-W7 Cada conversación se etiqueta con outcome: vendió/no vendió/handoff/abandono
ROG-W8 Datos de conversación nunca se usan para entrenar modelos de terceros
### ROG-S (Score Engine · 6 reglas)
ROG-S1 Score Engine de ARGOS es CLON independiente del motor del admin web · misma lógica, instancia separada
ROG-S2 Loanbook SISMO V2 es única fuente de verdad para entrenamiento del XGBoost · ambos motores leen el mismo dataset read-only
ROG-S3 Reglas duras ANTES del cálculo del score · si AUCO<70 o RiskSeal fraud o mora>$3M · rechazo inmediato sin llamar Claude
ROG-S4 Decisión siempre auditable · narrativa Claude persiste con timestamp + versión prompt
ROG-S5 Versiones XGBoost pineadas con joblib + hash · cada deploy registra hash en argos_events
ROG-S6 Notificación de decisión SOLO por WhatsApp en ARGOS · NO email (diferencia explícita vs admin web)

# 3. Score Engine clonado
## 3.1 Por qué clones y no integración compartida
El motor de score ya existe como Build 20 en el admin de www.roddos.com. La decisión del CEO es replicarlo dentro de ARGOS como clon independiente (ROG-S1) en lugar de exponerlo como API compartida. Razones:
Independencia operativa. Si el admin cae, ARGOS sigue vendiendo. Si ARGOS cae, el admin sigue vendiendo. Sin single point of failure.
Preparación para giro volumétrico. WhatsApp capturará 70-80% del volumen a futuro. Cuando eso pase, el flujo se invierte: el admin web empezará a delegar scoring al motor de ARGOS.
Aislamiento de blast radius (ROG-A11). Un compromiso en un sistema no compromete al otro.
Lo que SÍ se comparte: el loanbook de SISMO V2 como fuente de verdad para entrenamiento del XGBoost (ROG-S2). Ambos motores leen la misma cartera histórica read-only. Cada motor mantiene su propia tabla scoring_solicitudes con marca de origen (argos o web).
## 3.2 Arquitectura de 2 capas
Fiel al Build 20 original:
### Capa 1 — XGBoost con cartera real
Features: score externo (RiskSeal o Palenca según segmento) · capacidad de pago · estabilidad laboral · score comportamental (si cliente RODDOS) · validación biométrica · producto · tipo empleo · uso moto
Variable objetivo: default_90d (1 = mora >90 días o recuperación, 0 = pagó)
Fallback a regresión logística si dataset < 500 registros
Fallback a scorecard manual ponderado si dataset < 100 registros (fase inicial)
Re-entrenamiento weekly desde snapshot loanbook
### Capa 2 — Claude Sonnet 4.6 (razonamiento)
Analiza coherencia del KYC vs datos de partners
Detecta señales de fraude en documentos (extractos, desprendibles)
Genera ajuste cualitativo ±0.15 sobre probabilidad de default
Genera narrativa auditable (ROG-S4)
Score final = (0.7 × score_modelo + 0.3 × score_claude) × 1000
## 3.3 Reglas de producto

| Producto | Umbral default | Umbral cliente RODDOS A+ | Antifraude primario |
| --- | --- | --- | --- |
| Crédito RDX Leasing (moto) | 650 | 600 | AUCO + RiskSeal |
| Crédito Rodante (repuestos) | 500 | 400 (bypass) | RiskSeal dominante |

Para Crédito Rodante en cliente nuevo no-RODDOS, el peso de RiskSeal en el scorecard sube (35%) porque es el mejor detector de fraude de identidad — que es el principal riesgo en tickets bajos con cliente nuevo.
## 3.4 Reglas duras (ROG-S3)

| Regla | Umbral | Efecto |
| --- | --- | --- |
| AUCO score biométrico | < 70 | Bloqueo inmediato |
| RiskSeal fraud_flag | = true | Rechazo inmediato |
| Score Datacrédito (manual · no-delivery) | < 400 | Rechazo |
| Mora activa en centrales | > $3M COP | Rechazo |
| DTI declarado | > 60% | Rechazo |
| Fraude en documentos (Claude) | detectado | Rechazo + flag al analista |

## 3.5 Partners del Score Engine

| Partner | Función | Estado |
| --- | --- | --- |
| AUCO | Biometría facial + validación documento | Ya en uso · ARGOS replica credenciales (separadas) |
| RiskSeal | Digital footprint + antifraude · PRIMARIO para repuestos | Nueva integración · API REST simple |
| Palenca | Ingresos verificados delivery/mototaxi (OAuth) | Ya en uso · ARGOS replica |
| Datacrédito | Historial bancario tradicional · MANUAL (no API) | Solo en revisión manual del analista |
| process_document_chat | OCR + análisis Claude de desprendibles y extractos | Ya implementado · ARGOS replica |

## 3.6 Diferencia clave ARGOS vs admin web
Una sola diferencia operativa explícita por instrucción del CEO:
Admin web → notifica decisión por WhatsApp + email (redundancia)
ARGOS → notifica decisión SOLO por WhatsApp (ROG-S6)
Razón: en ARGOS todo el ciclo vive en WhatsApp · meter email rompe la experiencia. En el admin web el cliente llega por formulario que ya capturó email, tiene sentido confirmar ahí.

# 4. Los 6 flujos de negocio
Cada flujo se documenta por completo en docs/canonicas/flujos_negocio.md con paso a paso, eventos emitidos y actores. Aquí se presenta el resumen ejecutivo.
## 4.1 Mapa de los flujos

| # | Flujo | Foco | Duración objetivo |
| --- | --- | --- | --- |
| F1 | Onboarding y clasificación de intent | Captura opt-in + rutea a flujo correcto | < 30 seg primera respuesta |
| F2 | Venta TVS Raider con Crédito RDX Leasing | Puerta de entrada al cliente | < 5 min KYC a decisión |
| F3 ⭐ | Venta repuestos cliente RODDOS con Crédito Rodante | Negocio recurrente · bypass scoring | < 3 min cotización a pago |
| F4 | Venta repuestos cliente nuevo no-RODDOS | Captura lead · RiskSeal primario | < 5 min |
| F5 | Cobranza recurrente cuotas · RADAR + Wava | Salud financiera cartera | < 15 seg enviar link |
| F6 ⭐ | Mantenimiento predictivo + re-compra proactiva | Motor de LTV · anticipar necesidad | job semanal + conversión |

## 4.2 Por qué F3 y F6 son las joyas
F3 y F6 son los flujos marcados con estrella porque juntos forman el loop infinito de revenue recurrente.
F3 aplica bypass de scoring para cliente RODDOS con historial positivo (A+/A/B). Umbral 400 (vs 500 normal). Solo ejecuta RiskSeal como antifraude + XGBoost con features mínimas. Resultado en < 60 seg. Aprobación casi automática.
F6 ejecuta un job semanal que cruza customer_history × tabla de vida útil × uso intensivo. Detecta que Carlos mototaxista compró pastillas hace 7 meses → genera mensaje personalizado por WhatsApp → Carlos responde 'cotízame' → entra a F3 express → venta cerrada en 3 minutos.
El loop F3 ↔ F6 convierte a cada cliente que compra una moto en un cliente que compra 20+ repuestos durante los siguientes 5 años, sin necesidad de gasto de adquisición adicional.
## 4.3 F1 — Onboarding y clasificación de intent
Cliente envía primer mensaje a WhatsApp RODDOS. WhatsApp Agent solicita opt-in con template tappable. Procesa mensaje multimodal (texto, voz vía Whisper, imagen vía Claude vision). Clasifica intent con Haiku 4.5 en: cotizar_moto, cotizar_repuesto, pago_cuota, mantenimiento_consulta, soporte. Rutea al flujo correspondiente.
## 4.4 F2 — Venta TVS Raider con Crédito RDX Leasing
WhatsApp Agent envía Multi-Product Message con catálogo de motos (por ahora solo TVS Raider 125 · a futuro hasta 4 modelos). Cliente elige modelo y plan (9/12/18 meses). WhatsApp Agent abre KYC conversacional vía WhatsApp Flow nativo. Cliente envía selfie + documento. Score Engine evalúa reglas duras primero, luego consulta AUCO + RiskSeal + Palenca (si aplica) + process_document_chat, calcula XGBoost + Claude ajuste. Umbral 650 (cliente RODDOS A+ baja a 600). En < 5 min el cliente recibe resultado por WhatsApp. Si aprobado, link Wava para cuota inicial + handoff humano para coordinación logística.
## 4.5 F3 ⭐ — Venta repuestos cliente RODDOS
Cliente envía texto, nota de voz o foto de repuesto roto. Cotizador visual/voz identifica SKU con Claude vision (texto/imagen) o Whisper + Claude (audio). Cruza con SISMO inventario para stock + precio. Envía Multi-Product Message con producto premium/estándar/económico. Cliente elige o regatea. Si acepta y cliente es A+/A/B con monto < $500K: BYPASS aplicado (solo RiskSeal + XGBoost express · umbral 400 · resultado en 60 seg). Link Wava Nequi/Daviplata. Cliente paga sin salir de WhatsApp. Confirmación instantánea. Sistema agenda mantenimiento predictivo para F6 en T+meses.
## 4.6 F4 — Venta repuestos cliente nuevo no-RODDOS
Cotización igual a F3. Al cerrar, opciones: cash (RiskSeal aún se ejecuta como antifraude · ROG-S1) o Crédito Rodante (scoring full con RiskSeal dominante 35% del peso). Cliente queda registrado en SISMO · próxima compra ya es F3.
## 4.7 F5 — Cobranza recurrente
RADAR en SISMO V2 genera cobros semanales. ARGOS cobranza_orchestrator recibe el trigger vía webhook. Llama a Wava para crear link Nequi/Daviplata. WhatsApp Agent envía template utility ($0.0008 USD Colombia) con el link. Cliente paga sin salir de WhatsApp. Wava webhook → ARGOS → SISMO actualiza saldo. WhatsApp confirma al cliente. Si no paga en 24h: recordatorio suave. 48h: medio. 5 días: escalamiento a operador humano + impacta score_comportamental del cliente.
## 4.8 F6 ⭐ — Mantenimiento predictivo
Job semanal lunes 04:00. Por cada cliente activo: por cada repuesto consumible comprado en últimos 24 meses: si días_desde_compra / vida_útil_estimada está entre 0.85 y 1.05 (y uso intensivo reduce vida útil × 0.6) → candidato. Compliance Officer filtra por opt-in y por frecuencia (ROG-W5: max 1 mensaje cada 14 días). Strategist genera mensaje personalizado con Sonnet 4.6 (nombre + moto + repuesto + uso + LTV). WhatsApp Agent envía vía utility template. Respuesta del cliente dispara F3 express. Conversión proactiva → venta target > 12%.

# 5. Plan de trabajo v5
10 fases secuenciales que van de infraestructura bootstrap hasta comercialización a clientes externos. Cada fase se abre y se cierra formalmente con bitácora en docs/claude/phase_X.md.

| Phase | Título | Duración |
| --- | --- | --- |
| 0 | Bootstrap de infraestructura | Semana 1 |
| 1 | Marketplace MELI + Trends + Briefing v1 + SISMO Read + Impact Tracking | Semanas 2-4 |
| 2 | Score Engine clonado dentro de ARGOS | Semanas 5-6 |
| 3 | WhatsApp Agent + KYC + Flujos F1/F2/F3/F4 | Semanas 7-9 |
| 4 | Cobranza RADAR + Wava + Flujo F5 | Semana 10 |
| 5 | Mantenimiento predictivo F6 + Briefing v2 + GraphRAG + Evals | Semanas 11-12 |
| 6 | FB Marketplace + Ad Intelligence (Meta + Google) | Semanas 13-14 |
| 7 | Social Listening (IG + TikTok + YouTube) | Semana 15 |
| 8 | Media Buyer + CTW Ads + Compliance full | Semanas 16-17 |
| 9 | Comercialización a clientes externos | Mes 5+ |

Duración total del MVP interno (Phases 0-5): 12 semanas. Duración total para multi-tenant comercial (Phases 0-9): ~5 meses.
## 5.1 Phase 0 · Bootstrap
Repo scaffold + FastAPI + React + MongoDB Atlas + Render + CI/CD + dominio argos.roddos.com + Langfuse. En paralelo: setup de credenciales en Meta y Google Ads (System User ARGOS en BM existente + Service Account ARGOS en MCC existente · preserva histórico del pixel y learning · cumple ROG-A11 por separación de credencial), cuentas de partners creadas (Apify, ProxyRack, TikHub, SerpAPI, Anthropic, Wava, RiskSeal), credenciales AUCO y Palenca replicadas desde admin web.
## 5.2 Phase 1 · Marketplace + Briefing v1
Primera fase funcional. Marketplace Agent consume MELI, Trends con SerpAPI, Scout con Haiku, Strategist v1 genera briefing diario, Executive publica en /briefing y notifica por WhatsApp al CEO, SISMO lectura + impact tracking en T+7. El CEO recibe el primer Morning Briefing y aprueba/rechaza acciones con un tap.

## 5.3 Phase 2 · Score Engine (CRÍTICA)
Replicar el Build 20 completo dentro de ARGOS. Integración RiskSeal (nueva), AUCO + Palenca + process_document_chat (clonadas), XGBoost Capa 1, Claude Sonnet Capa 2, dashboard /scoring. Se testea vía API + dashboard con solicitudes sintéticas. No se conecta a WhatsApp todavía (eso es Phase 3).
## 5.4 Phase 3 · WhatsApp + KYC (CRÍTICA)
Activa el canal comercial completo. WhatsApp Agent base, intent classifier, cotizador visual (imagen + audio con Whisper), KYC conversacional con WhatsApp Flows, integración Wava para pagos, flujos F1/F2/F3/F4 end-to-end. Primera venta real de repuesto cerrada por WhatsApp. Primer Crédito Rodante aprobado vía WhatsApp.
## 5.5 Phase 4-9
Ver bitácoras individuales en docs/claude/phase_X.md para detalle de builds y criterios de cierre.

# 6. Metodología de trabajo
ARGOS replica la metodología probada de SISMO V2: tres carpetas .md que estructuran la arquitectura, evitan sobre-escribir trabajo, mantienen el contexto entre sesiones, y rompen los loops típicos cuando se trabaja con agentes IA como constructores.
## 6.1 Las 3 carpetas pilares

| Carpeta | Propósito | Contenido |
| --- | --- | --- |
| docs/canonicas/ | Mapa de conexiones del sistema | eventos.md, apis_internas.md, apis_externas.md, colecciones_mongo.md, integraciones_sismo.md, flujos_negocio.md |
| docs/claude/ | Bitácora arquitectónica por fase | Una entrada por phase con decisiones, errores, soluciones, aprendizajes + errores_recurrentes.md |
| docs/knowledge/ | Skills y configuraciones de agentes | 11 archivos agents/*.md + 6 archivos skills/*.md + stack.md + partners.md + modelos_llm.md |

## 6.2 CLAUDE.md raíz
Archivo raíz del repo que consagra las ROGs inamovibles, principios arquitectónicos, convenciones de código, política de commits, roles de trabajo. Es la primera lectura obligatoria de Claude Code al iniciar cualquier tarea. Cambios al CLAUDE.md requieren PR con aprobación explícita del CEO.
## 6.3 .planning/
Carpeta de prompts secuenciales para Claude Code. Un archivo por phase: phase_0_prompt.md, phase_1_prompt.md, etc. Cada prompt incluye: contexto previo de lectura obligatoria, objetivo de la phase, builds incluidos, reglas de operación, checklist final de cierre.
## 6.4 Roles de trabajo

| Rol | Quién | Responsabilidad |
| --- | --- | --- |
| Arquitecto / configurador | Claude.ai (yo) | Specs, prompts, canónicas, knowledge, audits |
| Constructor | Claude Code | Código, commits, tests, terminal, deployment |
| CEO / decisor | Andrés | Aprobaciones de phase, approvals de pauta y crédito |
| QA | Claude Code + smoke tests | TDD obligatorio en módulos críticos (Score, Wava, Media Buyer) |

## 6.5 Flujo operativo por phase
Claude.ai entrega el prompt detallado en .planning/phase_X_prompt.md y abre bitácora vacía docs/claude/phase_X.md
CEO revisa el prompt y confirma arranque
Claude Code lee CLAUDE.md + canónicas + knowledge relevantes + errores_recurrentes.md ANTES de codear
Claude Code ejecuta cada build. Cada PR actualiza canónicas afectadas + bitácora del phase
Errores >30 min de debug se registran inmediatamente en errores_recurrentes.md
Al cierre: checklist de phase verde → tag phase-X-closed → Claude.ai prepara prompt de phase siguiente

# 7. Presupuesto y riesgos
## 7.1 Costos operativos mensuales · post-Phase 5

| Concepto | USD/mes | COP/mes (TRM 4000) |
| --- | --- | --- |
| Render Starter backend | $7 | $28.000 |
| Render Static Site frontend | $0 | $0 |
| MongoDB Atlas M10 + backups nativos + PITR | $57 | $228.000 |
| Qdrant + Redis self-hosted en Render | $0 | $0 |
| Render Persistent Disk (creatives + modelos) | $10-20 | $40.000-80.000 |
| Anthropic API (Sonnet + Haiku + Opus con caching) | $130-180 | $520.000-720.000 |
| Apify (FB MP + Ad Library) | $80-150 | $320.000-600.000 |
| ProxyRack residenciales | $80-120 | $320.000-480.000 |
| TikHub.io | $30-50 | $120.000-200.000 |
| SerpAPI (5K queries) | $50 | $200.000 |
| Langfuse self-hosted | $0 | $0 |
| Subtotal infra + APIs | ~$650-850 | ~$2.6M-3.4M COP |

Adicional (no fijo):
Mercately · WhatsApp pricing Meta · utility templates $0.0008 USD Colombia · marketing $0.0125 USD
Wava · comisión ~2.9% por transacción procesada (es costo de venta, no de infra)
RiskSeal · por consulta · negociar paquete según volumen
AUCO y Palenca · por consulta · negociar paquete
Pauta digital ejecutada por Media Buyer · es presupuesto de marketing, no de ARGOS · sujeto a spending caps en código (ROG-A2)

## 7.2 Riesgos críticos

| # | Riesgo | Mitigación |
| --- | --- | --- |
| R1 | Meta o Google demoran en aprobar extensión de permisos para CTW ads sobre BM/MCC existente | Extensiones sobre cuenta existente son más rápidas (1-2 semanas) que review de cuenta nueva (4-6 semanas) · si demora, Phases 1-7 no dependen · Phase 8 es la que espera |
| R2 | Wava settlement martes/viernes crea gap de caja | SISMO V2 tiene buffer · flujo F5 no depende de settlement inmediato |
| R3 | RiskSeal no tiene contrato cerrado · pricing incierto | PoC gratis en Phase 0 · fallback si pricing es prohibitivo: RiskSeal solo para repuestos (no moto) + reducir scope de llamadas |
| R4 | Scraping FB Marketplace y Meta Ad Library bloqueados por Meta | Apify como provider + Scrapling fallback con proxies residenciales · ROG-A8 |
| R5 | Drift de modelos Claude entre versiones rompe Strategist | Versiones pineadas en código · canary contra dataset de evals · Phase 5 incluye sistema de evals obligatorio |
| R6 | Prompt injection desde contenido scrapeado (ads competitivos) manipula Strategist | Separación clara user_instruction vs scraped_content · sanitización · documentado en CLAUDE.md como untrusted data |
| R7 | Score Engine clonado diverge del admin web sin que nadie se dé cuenta | Dataset compartido (loanbook SISMO) · tests SC-01 a SC-19 idénticos · auditorías periódicas CEO |
| R8 | Cliente usa WhatsApp para queja y AI responde mal · daño reputacional | ROG-W4: handoff humano obligatorio en quejas · logging completo de handoffs |
| R9 | Meta cambia política de utility templates y sube 10x el costo | Monitoreo mensual de pricing · contrato Mercately con cláusula de pass-through · fallback SMS en casos extremos |
| R10 | Costos Anthropic se disparan por volumen WhatsApp agresivo | Prompt caching obligatorio · Haiku para intent classification · Batch API para reportes · alertas Langfuse si costo diario > 2x baseline |

# 8. Decisiones pendientes antes de Phase 0
10 decisiones del CEO que deben responderse antes de arrancar Phase 0. La mayoría ya están implícitamente resueltas por la iteración de esta semana; se listan para cerrar formalmente con respuestas escritas.

| # | Decisión | Mi recomendación |
| --- | --- | --- |
| 1 | Pre-aprobar presupuesto operativo ~$650-850 USD/mes | Sí |
| 2 | MongoDB Atlas M2 desde Phase 0 · M10 desde Phase 2 (cuando ingesta FB MP) | Sí · ahorra ~$150 primeros 2 meses |
| 3 | Credenciales Meta para ARGOS · System User dedicado dentro del BM RODDOS existente (no cuenta nueva) | Sí · preserva histórico pixel + learning · aislamiento por credencial (ROG-A11) |
| 4 | Credenciales Google Ads · Service Account dedicado dentro de la MCC RODDOS existente (no MCC nueva) | Sí · preserva quality scores + conversions · aislamiento por credencial (ROG-A11) |
| 5 | Quién aprueba pauta · Iván CGO | Principal: CGO · Backup: CEO |
| 6 | Spending caps default del CLAUDE.md | Sí · ajustables después |
| 7 | Confirmar Render para backend + frontend (mismo patrón SISMO V2) | Sí |
| 8 | Comprar dominio getargos.ai ahora o después | Ahora · $60/año asegura el nombre |
| 9 | Workspace primario RODDOS con verticals REPUESTOS-MOTOS + MOTOS | Sí · verticals separados |
| 10 | Iniciar Wava onboarding ya (no esperar Phase 4) | Sí · el proceso toma 2-3 semanas |

## 8.1 Checklist final para arrancar Phase 0
10 decisiones respondidas por el CEO
Paquete de archivos .md de Visión 2.0 copiado a carpeta ARGOS/ en Desktop
Repo RoddosColombia/ARGOS creado (vacío) en GitHub con branch protection
Trabajo paralelo en SISMO V2: exponer endpoints de lectura listados en docs/canonicas/integraciones_sismo.md
Claude Code apuntado a la carpeta ARGOS/ del Desktop
Primer prompt listo en .planning/phase_0_prompt.md

# 9. Próximo paso
## 9.1 Qué hacer con este paquete
El paquete que acompaña este documento contiene 42 archivos .md organizados en la estructura CLAUDE.md + docs/canonicas/ + docs/claude/ + docs/knowledge/ + .planning/
Copiarlo tal cual a una carpeta ARGOS/ en el Desktop · NO reorganizar
Abrir Claude Code · apuntar al directorio ARGOS/ · iniciar sesión
Darle como primer prompt: 'Lee /CLAUDE.md y luego /.planning/phase_0_prompt.md. Ejecútalo paso a paso. Al cerrar cada build actualiza docs/claude/phase_0_bootstrap.md'
Claude Code arranca con conocimiento completo del sistema y no empieza de cero
## 9.2 Pre-requisito del CEO en paralelo a Phase 0
Andrés debe coordinar en paralelo:
Creación de cuentas: Wava (onboarding · 2-3 semanas), RiskSeal (PoC gratis), Anthropic dedicada ARGOS, Apify, ProxyRack, TikHub, SerpAPI
App reviews iniciados: Meta Business Manager ARGOS, Google Ads MCC ARGOS
Trabajo sobre SISMO V2: equipo que mantiene SISMO expone los 4 endpoints de lectura documentados en docs/canonicas/integraciones_sismo.md · estimado 2-3 días de Claude Code sobre el repo SISMO
Replicación de credenciales AUCO y Palenca (separadas del admin web · ROG-A11)
Captura de baseline operativo de RODDOS (ventas, rotación, margen, ROAS · Phase 0 Build 0.9)
## 9.3 Qué esperar en las próximas 12 semanas
Después de 12 semanas (Phase 5 cerrada):
ARGOS recibe ventas por WhatsApp de repuestos todos los días
Morning Briefing diario 5:30 AM con top 3 acciones aprobables con un tap
Score Engine evalúa solicitudes en < 5 min · notificación SOLO por WhatsApp
Cobranza semanal automatizada vía Wava · Nequi + Daviplata sin fricción
Mantenimiento predictivo envía mensajes a clientes maduros · conversión > 10%
Inteligencia de mercado alimentando decisiones · ROAS pauta digital optimizado
Después de 5 meses (Phase 9 cerrada):
Multi-tenant operativo · primeros clientes externos onboardeados
MCP server público en getargos.ai expone ARGOS como herramienta para otros agentes IA
MRR inicial de clientes externos > $2K USD

## 9.4 Cierre
Este documento y el paquete de archivos .md son la v2.0 completa del plan. Todo cambio posterior se gestiona por PR al documento maestro (que se commiteará como docs/VISION_2_0.md en el repo al momento de arranque) o a las canónicas correspondientes. La versión vive. Se cuida.
La tesis sigue siendo la misma que en la primera iteración: convertir la venta de una moto en una relación de 5 años de repuestos recurrentes, automatizar el contacto con los clientes por WhatsApp como frontend comercial, y usar un cerebro agéntico que aprende de cada decisión. Lo único que cambió en Visión 2.0 es que ahora está construible sin supuestos erróneos: con el motor de score como clon interno, con Wava para Nequi/Daviplata, con RiskSeal como antifraude primario de repuestos, y con la metodología probada de SISMO V2 como columna vertebral de arquitectura.
Nos vemos en Phase 0.