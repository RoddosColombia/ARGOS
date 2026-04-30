# ARGOS — Visión 2.1

> **Documento ejecutivo maestro · supersede `VISION_2_0.md` en las secciones que cambian.**
> Versión 2.1 · 29 de abril de 2026 · Aprobada por Andrés San Juan (CEO)
> Cambio de tesis: ARGOS deja de ser "tienda super poderosa en WhatsApp + Inteligencia de Mercado" para articularse como **sistema operativo de una nueva categoría de venue de comercio de repuestos moto en Colombia**, con la tesis explícita de desplazar a Mercado Libre como venue dominante en 18 meses.
> `VISION_2_0.md` se preserva como referencia histórica.

---

## 0. Resumen ejecutivo de la 2.1

Visión 2.1 mantiene la tesis comercial recurrente de Visión 2.0 (cada moto vendida es un cliente para 5 años de repuestos) pero la subordina a una tesis competitiva más grande: **ARGOS no compite con otros sistemas de inteligencia comercial; compite con MELI por la ocupación mental del cliente que necesita un repuesto moto**.

El cambio no es retórico. Reordena la arquitectura, el cronograma y la governance:

- ARGOS opera sobre siete moats que MELI estructuralmente no tiene (sección 1)
- La arquitectura crece a 14 componentes con tres componentes nuevos: SKU canonicalizer, Portfolio agent, Account intel agent (sección 2)
- El Score Engine es pass-through al repo `roddos-scoring` por governance crediticia única, no clon (sección 3)
- Cobranza recurrente sale del scope de ARGOS y queda íntegra en SISMO (sección 4)
- Output unificado a CEO + CGO con mismo brief, mismo formato, mismo timing — diferenciado solo en approval rights por plano (sección 5)
- Cronograma operativo de ~26 semanas para tener la operación completa, ~6 meses, dejando 12 meses de ejecución para cumplir tesis 18 meses (sección 6)
- Crecimiento target: x3 mes a mes durante la ventana de oportunidad (4-6 meses iniciales · sección 7)

**Recomendación**: PROCEDER a Phase 2.5 · alineación. Antes de meter código de Phase 3 (WhatsApp commerce), se ejecutan tres semanas de plomería que cierran las contradicciones documentales de Phase 0/1/2 e instalan los rieles que Capa 1 va a usar. Sin esto, Phase 3 hereda deuda silenciosa al canal de revenue.

---

## 1. La tesis competitiva de 18 meses

### 1.1 Por qué MELI es vulnerable en repuestos moto

Mercado Libre es el venue de ecommerce dominante en LATAM. Para la mayoría de categorías ese dominio es defendible — escala, logística, reputación de vendedores, payment integrado. Pero para una categoría tan recurrente y tan vinculada al vehículo personal del cliente como repuestos moto, MELI es genérico de manera que invita a un challenger especializado.

MELI no sabe qué moto tiene el cliente. No sabe cuándo cambió por última vez sus pastillas. No le financia un repuesto de $80K en 60 segundos sin papeleo. No le sugiere proactivamente que es momento de cambiar el aceite. No aprende de cada cliente para mejorar la próxima conversación. Para el mototaxista o delivery que usa la moto 2x-2.5x más intensivo y que consume 6-12 repuestos al año, esas limitaciones no son detalles — son fricción acumulada.

### 1.2 Los siete moats de ARGOS vs MELI

ARGOS gana esta categoría si ejecuta bien sobre siete palancas que MELI no tiene y que estructuralmente no puede tener al mismo nivel:

**Moat 1 · Velocidad superior.** MELI: 15-25 minutos desde búsqueda hasta pago confirmado. ARGOS WhatsApp bien hecho: <5 minutos. La diferencia se sostiene si la plataforma técnica de ARGOS no se cae nunca en P95. Una sola conversación caída por timeout en Wava o SISMO en el momento de cierre y el cliente regresa al comportamiento MELI.

**Moat 2 · Crédito instantáneo.** Crédito Rodante con bypass para cliente RODDOS A+/A/B: 60 segundos. Mercado Crédito: 24-72 horas con fricción. Este moat depende íntegramente de la disciplina del Score Engine (pass-through a `roddos-scoring`) + RiskSeal para nuevos.

**Moat 3 · Memoria del cliente.** ARGOS sabe qué moto tiene cada cliente, su historial de mantenimiento, su uso intensivo, sus preferencias de tier (premium/estándar/económico). MELI estructuralmente no puede saberlo porque no es relación, es transacción. F6 mantenimiento predictivo es la materialización de este moat.

**Moat 4 · Diagnóstico conversacional.** "Mi moto hace ruido al frenar" → Claude vision identifica problema, sugiere SKU compatible, ofrece. MELI requiere que el cliente ya sepa qué SKU buscar. Para mototaxistas no-mecánicos, esta brecha es enorme.

**Moat 5 · Catálogo curado y stock garantizado.** En MELI compite cualquier vendedor con SKUs duplicados, precios erráticos y reviews dispersas. En ARGOS hay un solo vendedor (RODDOS) con catálogo curado, stock real, pricing competitivo y SKU normalizado. Si Portfolio agent + Pricing engine + SKU canonicalizer hacen su trabajo, en los SKUs que importan el cliente no tiene incentivo para ir a MELI.

**Moat 6 · Loop relacional con cobranza propia.** Cliente que paga via Wava + queda en SISMO recurrente queda enganchado al ecosistema RODDOS. Cliente MELI compra una vez y se evapora. La cobranza vive en SISMO (no en ARGOS), pero el efecto de retención es el mismo: el cliente no es de un seller, es de RODDOS.

**Moat 7 · Velocidad de aprendizaje.** Cada conversación enriquece ARGOS — nuevos SKUs preguntados, nuevos síntomas, nuevos competidores mencionados. MELI no aprende sobre tu cliente porque tu cliente no es su cliente. Este moat compone exponencial: en 18 meses ARGOS sabe cosas sobre el mototaxista colombiano que MELI no puede aprender.

### 1.3 Lo que la tesis 18 meses NO significa

No es que ARGOS reemplace a MELI globalmente. Es que en la categoría específica de repuestos moto en la geo donde RODDOS opera, el reflejo del cliente cambie de "voy a buscar en MELI" a "le pregunto a RODDOS por WhatsApp". Eso ya es ganar la categoría. La presencia en MELI sigue importando como canal de adquisición — pero el cierre se traslada al WhatsApp y la repetición se gana en la conversación.

### 1.4 ADN moto preservado

Esta tesis no diluye el foco moto. Las motos siguen siendo la puerta de entrada al cliente y el insumo del loanbook que alimenta todo lo demás. F2 (TVS Raider con RDX Leasing) es el flujo que más automatización merece, no menos: cierre conversacional completo, KYC vía WhatsApp Flow, AUCO biometría, Score Engine, Wava cuota inicial, SISMO `loans/initiate` automático, logistics handoff vía notificación al equipo (no operador llenando forms manualmente). El criterio del CEO es claro: **robustez sobre velocidad, automatización completa en ambos verticales**.

---

## 2. Arquitectura de 14 componentes

ARGOS sigue siendo un sistema multi-agente sobre bus de eventos append-only (`argos_events`), con agentes stateless y estado en el bus (ROG-A7). La 2.1 expande de 11 a 14 componentes para soportar la tesis competitiva:

### 2.1 Los 14 componentes

**Núcleo de inteligencia (sensing + entendimiento) — 5 componentes:**

1. **Scout** · descubre SKUs y nichos emergentes vía consultas configurables sobre MELI/Apify/SerpAPI.
2. **Marketplace** · ingesta MELI + FB Marketplace + extensión a TikTok Shop e Instagram Shopping (nuevo en 2.1).
3. **Trends** · señales de demanda Google Trends + búsquedas MELI + hashtags TikTok.
4. **Competitors** · ingest de Meta Ads + Google Ads + Mercado Libre Ads transparency (extensión 2.1).
5. **Social** · TikHub para top accounts y engagement por nicho moto.

**Núcleo de inteligencia avanzada (entendimiento + síntesis) — 3 componentes nuevos en 2.1:**

6. **SKU canonicalizer** · normaliza identidad de SKU entre fuentes (MELI, FB MP, scraping, SISMO interno) usando embeddings + LLM tie-breaking + tabla de aliases que se enriquece con cada normalización exitosa. Es prerequisito técnico para que los streams de inteligencia se crucen accionablemente.
7. **Portfolio agent** · agente nuevo, weekly run lunes 06:00, cruza demanda de mercado por SKU canonical × stock RODDOS × velocidad rotación competitiva × margen estimado, y emite recomendaciones de portfolio: SKUs huérfanos (alta demanda, no stockeados), sub-stockeados, en deprecación, categorías emergentes, cross-sell gaps. Output al brief unificado CEO/CGO.
8. **Account intel agent** · trackea continuamente top vendedores MELI + top cuentas TikTok/IG en nicho moto. Sub-servicio `meli_sellers` y `social_accounts`. Extrae playbook por competidor: cadencia de promo, tipo de creative, audiencias inferidas, movimientos por replicar y movimientos por evitar. Eventos `competitor.meli.*` y `competitor.social.*` al bus.

**Núcleo de decisión y ejecución — 4 componentes:**

9. **Strategist** · sintetiza eventos del bus + perfiles competitivos + impact tracking en recomendaciones priorizadas. Modelo Opus 4.7 para razonamiento complejo, Sonnet 4.6 para síntesis de brief.
10. **Pricing engine** · agente dedicado en 2.1 (en 2.0 implícito en Strategist). Cada SKU activo recibe sugerencia de precio diaria con contexto competitivo y envelope de margen. Acciones Plano 1 dentro de envelope se ejecutan automáticamente; Plano 2/3 escalan.
11. **Media Buyer** · ejecución de pauta Meta + Google + TikTok con creative variations + lookalikes + bidding data-driven. Adelantado a Capa 5 (semanas 22-27), no Phase 8.
12. **Compliance Officer** · enforza ROGs en código + valida spending caps + opera los tres planos de approval (Plano 1 envelope automático, Plano 2 CGO, Plano 3 CEO). Adelantado a Capa 0 en versión Plano 1.

**Núcleo de canal y aprendizaje — 2 componentes:**

13. **WhatsApp Agent** · frontend conversacional. Mercately webhook + intent classifier + cotizador multimodal + WhatsApp Flow KYC + Wava + SISMO write. Sirve flujos F1/F2/F3/F4/F6 (F5 cobranza queda en SISMO).
14. **Executive (briefing unificado)** · produce brief diario y semanal entregado simultáneamente y con contenido idéntico a CEO + CGO. Diferenciación solo en cola de approvals según role.

### 2.2 Capas operativas

ARGOS opera en cuatro motores que se materializan a partir de los 14 componentes:

**Motor de comercio conversacional** · WhatsApp Agent + Wava + SISMO bidireccional + Score Engine pass-through. Cierra ventas, solicita facturación. Es el frontend.

**Motor de inteligencia de mercado** · Scout + Marketplace + Trends + Competitors + Social + SKU canonicalizer + Portfolio + Account intel. Observa el ecosistema digital de repuestos y produce conocimiento accionable.

**Motor de decisión y ejecución** · Strategist + Pricing engine + Media Buyer + Compliance Officer. Convierte conocimiento en acciones, dentro o fuera de envelope, dirigidas al canal o al portafolio o al CEO/CGO.

**Motor de aprendizaje** · Impact tracking del Strategist + Memory + per-conversation outcomes (ROG-W7). Cierra el loop midiendo qué funcionó y ajusta los pesos de los modelos predictivos.

### 2.3 Las 4 categorías de Reglas de Oro

ROGs son inamovibles (CLAUDE.md sección 3). Las 4 categorías post-2.1:

- **ROG-A · ARGOS core** (12 reglas) · multi-tenancy, bus, audit, aislamiento, etc.
- **ROG-W · WhatsApp** (8 reglas) · opt-in, frecuencia, handoff, outcomes.
- **ROG-S · Score Engine** (6 reglas) · pass-through a `roddos-scoring`, governance crediticia única.
- **ROG-G · Governance multi-role** (4 reglas, nuevas en 2.1) · planos 1/2/3, output unificado CEO/CGO, role-based approvals, audit por role.

---

## 3. Score Engine pass-through

Visión 2.0 sección 3 describía el Score Engine como **clon independiente** del motor del admin web. Esa decisión se revirtió formalmente el 2026-04-27 por instrucción del CEO. Visión 2.1 documenta la nueva postura.

### 3.1 Score Engine vive en `roddos-scoring`

El motor de score crediticio de RODDOS es un repo independiente operado por Iván Echeverri (`https://github.com/RoddosColombia/roddos-scoring`). Tanto el admin web (`www.roddos.com`) como ARGOS lo consumen vía API HTTP. ARGOS no replica lógica crediticia; hace pass-through del payload, recibe la decisión y la procesa.

### 3.2 Por qué pass-through y no clon

La razón estratégica original de Visión 2.0 ("aislamiento de blast radius", "preparación para giro volumétrico", "independencia operativa") se sustituye por una razón distinta y más fuerte en la realidad operativa actual: **governance crediticia única**. Cambios de pesos del XGBoost, integración nueva con Datacrédito si llega API, eventual auditoría SuperFinanciera y reglas duras (AUCO<70, RiskSeal fraude, mora>$3M) son responsabilidad del repo `roddos-scoring` bajo ownership de Iván. Duplicar el motor multiplica el costo regulatorio y la complejidad de governance, sin ganar suficiente.

### 3.3 Política de degradación

Si `roddos-scoring` está caído, ARGOS pausa nuevas aprobaciones de crédito (no aprueba sin score) pero **sigue procesando** ventas cash, F4 cash, consultas de stock, cotizaciones, recomendaciones, briefs. El blast radius operativo queda contenido al flujo crediticio.

### 3.4 Contrato API auditable

ARGOS preserva en `docs/canonicas/score_engine_contract.md` el schema JSON versionado del endpoint `/v1/evaluate` + 1 test de contrato corriendo en CI semanal que valida que el response sigue cumpliendo el schema. Si Iván cambia el schema sin avisar, el test falla y se notifica antes de que rompa producción.

### 3.5 Audit local

Aunque el Score Engine audita en su propio side, ARGOS persiste en `audit_log` propio cada llamada a `/evaluate` con: timestamp, workspace_id, actor (role + user), payload enviado (sin PII), decision recibida, engine_version. Cumple ROG-A12 lado-Argos.

### 3.6 Diferencia ARGOS vs admin web

Una sola diferencia operativa, igual que en Visión 2.0:

- Admin web: notifica decisión crediticia por WhatsApp + email
- ARGOS: notifica solo por WhatsApp (ROG-S6)

Razón: en ARGOS todo el ciclo vive en WhatsApp · email rompe la experiencia. En el admin web el cliente llega por formulario que ya capturó email.

---

## 4. Los 6 flujos de negocio · actualizados

### 4.1 Mapa de flujos

- F1 · Onboarding y clasificación de intent (ARGOS)
- F2 · Venta TVS Raider con Crédito RDX Leasing (ARGOS · automatización completa)
- F3 ⭐ · Venta repuestos cliente RODDOS con bypass (ARGOS · automatización completa)
- F4 · Venta repuestos cliente nuevo no-RODDOS (ARGOS)
- ~~F5 · Cobranza recurrente~~ → **MOVIDO A SISMO** (ver sección 4.7)
- F6 ⭐ · Mantenimiento predictivo (ARGOS · ejecuta job semanal y dispara F3 express)

### 4.2 F3 ⭐ y F6 ⭐ son las joyas (sin cambios)

F3 + F6 forman el loop infinito de revenue recurrente. F3 vende a cliente RODDOS con bypass (umbral 400 vs 500 normal · solo RiskSeal antifraude + XGBoost express · resultado <60 seg). F6 ejecuta job semanal que cruza customer_history × tabla vida útil × uso intensivo y dispara mensaje proactivo que entra a F3 express. Conversión target ≥10% en cohortes de 200+ clientes.

### 4.7 F5 cobranza · fuera de scope ARGOS

Visión 2.0 sección 4.7 incluía F5 dentro de ARGOS con `cobranza_orchestrator` recibiendo trigger de RADAR vía webhook, generando link Wava, enviando template utility por WhatsApp Agent, escalando a humano si no paga, e impactando `score_comportamental`. **Visión 2.1 saca F5 íntegro de ARGOS.**

Razón: SISMO V2 ya tiene RADAR, ya tiene integración Mercately desde Build 14, ya tiene Wava operativo (en proceso de onboarding). El ciclo de cobranza recurrente vive completo en SISMO con su propio canal WhatsApp. ARGOS termina donde empieza la facturación: cierra venta, solicita invoice a SISMO con validaciones, deja al cliente activo en el loanbook. Lo que sigue es responsabilidad de SISMO.

ARGOS no dispara ni procesa cobranza (corrección a CLAUDE.md sección 9). El blast radius operativo queda más limpio: ARGOS gana ventas y SISMO gestiona el ciclo financiero.

### 4.8 Integración bidireccional ARGOS ↔ SISMO

La pieza nueva que Visión 2.1 documenta formalmente es la dirección **ARGOS → SISMO de escritura**, prerequisito de la automatización completa que el CEO solicitó. SISMO debe exponer cuatro endpoints:

- `POST /api/sismo/invoices` · payload con customer_id + line_items + payment_ref Wava + channel="argos_whatsapp" → SISMO valida (stock real, precio vigente, customer activo, idempotency por payment_ref) → factura → response con invoice_number.
- `POST /api/sismo/customers/activate` · para cliente nuevo de F4 (cuando paga cash con RiskSeal antifraude OK).
- `POST /api/sismo/loans/initiate` · para F2 (cuando Score Engine aprueba RDX Leasing y Wava confirma cuota inicial).
- `POST /api/sismo/payments/confirm` · para confirmaciones de pago Wava que ARGOS recibe y SISMO debe registrar.

Sin estos endpoints disponibles, F3/F4/F2 quedan a medias — un humano facturando manualmente al final. **Esto es trabajo paralelo de coordinación con el equipo de SISMO**, kick-off antes de empezar Capa 1 de ARGOS.

Spec detallada del schema de cada endpoint vive en `docs/canonicas/integraciones_sismo.md` ampliada en Capa 0.

---

## 5. Output unificado CEO + CGO

Visión 2.0 asumía implícitamente que el CEO recibe todo y aprueba todo. Visión 2.1 explicita el modelo multi-role:

### 5.1 Información idéntica para ambos roles

Todos los reportes, briefs, dashboards y documentación se entregan **simultáneamente, mismo formato, mismo contenido** a CEO (Andrés San Juan) y CGO (Iván Echeverri). No hay versión cliente-side ni delegación de información. Esto:

- Mantiene a ambos sincronizados informacionalmente todo el tiempo
- Da accountability mutua sin opacidad
- Simplifica la arquitectura del Executive: un solo pipeline de briefing, no dos
- Refuerza que ARGOS es transparente entre los líderes que lo gobiernan

### 5.2 Approval rights diferenciados en código (3 planos)

Lo que difiere es a quién le toca firmar qué. Compliance Officer enforza esta separación en código:

**Plano 1 · Reversibles dentro de envelope.** Ejecutadas por ARGOS automáticamente. Log al cierre del día visible a ambos. Ej: ajuste de bid Meta entre ±10%, pausa de ad set CTR<X durante Y horas, ajuste precio MELI dentro de banda margen [piso, techo], sugerencia de creative dentro de pool aprobado. Compliance Officer enforza el envelope.

**Plano 2 · Tácticas con costo material.** Aprobadas por **CGO**, no CEO. Ej: lanzar nuevo creative, expandir budget de campaña +25%, abrir nueva audiencia lookalike, descuento puntual en SKU, cambio de cadencia promo. Approval flow vía WhatsApp tap o frontend. Si CGO no aprueba en 24h, default rechazo y notificación al CEO.

**Plano 3 · Estratégicas.** Aprobadas por **CEO**. Ej: entrar a nueva categoría de repuesto, cambiar margen piso, integrar nuevo partner, decisión de portfolio expansion (qué SKUs sourcear), spending caps mensuales totales, cambios estructurales del Compliance Officer.

### 5.3 Implementación

- Schema `users` admite role nativo: `ceo`, `cgo`, `analista`, `sistema`, `cliente`. Hoy existe campo `role` pero `cgo` no era nativo.
- `auth/deps.py` valida role-based access a endpoints de approval.
- `recommendations` agrega campo `approval_required_role: ceo | cgo | none`. Si `none` y dentro de envelope Plano 1, Compliance Officer ejecuta sin tap humano.
- Frontend: dashboard idéntico para ambos roles, columna lateral "tu cola de aprobaciones" filtrada por role del JWT.
- WhatsApp: notificación igual a ambos pero CTA dirigido al role apropiado cuando corresponde aprobación.
- ROG-A12 audit_log registra qué role aprobó qué, dando accountability mutua.

---

## 6. Cronograma operativo · 6 capas en 26 semanas

Visión 2.0 estimaba MVP en 12 semanas (Phases 0-5). Visión 2.1 propone 26 semanas para tener la operación completa funcionando con la robustez que el CEO exige. Phases 0 y 1 ya están cerradas (~6 semanas hechas en abril). El cronograma siguiente arranca con Phase 2.5 · alineación.

### Capa 0 · Phase 2.5 · Alineación y plomería · semanas 1-3

Sin código de negocio nuevo. Objetivo: dejar el muro de carga firme antes de tocar Phase 3.

Builds principales: alineación documental (CLAUDE.md + canónicas), audit_log writers, collection contacts + opt-in, Compliance Officer Plano 1, CGO role nativo, score_engine_contract.md + test CI semanal, SISMO bidirectional spec en canónicas, Builds 0.6-0.9 cleanup (Langfuse, baseline), scheduler persistente.

Detalle ejecutable en `.planning/phase_2.5_prompt.md`.

### Capa 1 · Phase 3 foundation · semanas 4-7

Plataforma WhatsApp + Wava + SISMO bidireccional + brief unificado CEO/CGO. Mercately webhook + outbound engine, conversation state machine con outcomes obligatorios, Wava integration completa con idempotency, 4 endpoints SISMO de escritura implementados (asumiendo que SISMO los expuso en paralelo), cola persistida para invoicing pendiente, Multi-Product Message scaffolding, WhatsApp Flow runner base, cotizador multimodal Whisper + Claude vision.

### Capa 2 · F3 + F4 repuestos · semanas 8-11

Flujos comerciales más simples primero. F4 cliente nuevo cash (RiskSeal antifraude). F4 cliente nuevo crédito (RiskSeal 35% en scorecard, umbral 500). F3 cliente RODDOS bypass (lectura score_comportamental loanbook + bypass A+/A/B + RiskSeal antifraude + ScoreEngineClient express + umbral 400 + <60 seg). ROG-W2 piso de margen en código.

Validation: 50+ ventas reales cerradas por WhatsApp con SISMO facturando automático, cero violaciones opt-in, cero ventas duplicadas por race condition.

### Capa 3 · F2 motos + F1 onboarding · semanas 12-16

F1 onboarding al primer mensaje. F2 catálogo motos con Multi-Product Message + WhatsApp Flow KYC nativo + AUCO biometría + ScoreEngineClient con XGBoost full + Wava cuota inicial + SISMO `loans/initiate` + logistics handoff automatizado.

Validation: 5+ motos vendidas por WhatsApp end-to-end, satisfacción cliente medible.

### Capa 4 · F6 + extensión sensing layer + 3 componentes nuevos · semanas 17-21

F6 mantenimiento predictivo: weekly job que dispara F3 express a clientes con repuestos próximos a vencer.

Construcción de los 3 componentes nuevos de 2.1:
- **SKU canonicalizer** como servicio de primera clase (prerequisito para Portfolio + Account intel).
- **Portfolio agent** con weekly brief de SKUs huérfanos / sub-stockeados / emergentes / cross-sell.
- **Account intel agent** con sub-servicios `meli_sellers` y `social_accounts`, extracción de playbook semanal por competidor.

Extensión sensing layer: TikTok Shop + IG Shopping + scraping competencia top 20 + Mercado Libre Ads transparency.

### Capa 5 · Pricing engine + Media Buyer + Compliance Plano 2/3 maduro · semanas 22-27

Pricing engine como agente dedicado: sugerencia diaria SKU por SKU dentro de envelope.
Media Buyer: ejecución de pauta Meta + Google + TikTok con creative variations + lookalikes + bidding data-driven.
Compliance Officer maduro: tres planos operativos completos.

Validation: x3 mensual sostenido posible (ver sección 7).

### Resumen

| Capa | Semanas | Foco |
|---|---|---|
| 0 | 1-3 | Alineación + plomería |
| 1 | 4-7 | Foundation WhatsApp + Wava + SISMO write |
| 2 | 8-11 | F3 + F4 repuestos |
| 3 | 12-16 | F2 motos + F1 onboarding |
| 4 | 17-21 | F6 + sensing extendido + 3 componentes nuevos |
| 5 | 22-27 | Pricing + Media Buyer + Compliance maduro |

Total: ~27 semanas (6 meses). Después: 12 meses de ejecución operativa para cumplir tesis 18 meses.

---

## 7. Crecimiento target · x3 mensual durante ventana

### 7.1 Por qué x3 es alcanzable durante 4-6 meses

X3 mensual sostenido durante muchos meses tiene techo natural en un mercado acoplado a parque vehicular existente. Pero la tesis 2.1 no requiere x3 sostenido indefinido — requiere **x3 durante la ventana de oportunidad** donde la palanca aún tiene recorrido (4-6 meses iniciales) y crecimiento alto sostenido después.

Las palancas que palanquean x3 durante esa ventana:

- **Activación de base instalada** vía F6 mantenimiento predictivo. Sobre clientes RODDOS existentes, F6 con conversión 12% = 360+ ventas/mes incrementales sobre base de 3,000 clientes activos. Palanca más barata.
- **Captura de demanda activa** vía SOV en MELI + Meta + Google + TikTok. Pricing dinámico + listings optimizados + audiencias lookalike. Palanca media.
- **Expansión de portfolio** vía recomendaciones del Portfolio agent. SKUs nuevos = revenue nuevo de mercado no atacado. Palanca alta pero con lead time de sourcing.
- **Conversión de tráfico social** vía contenido externo (fuera de ARGOS) + ARGOS sugiriendo qué SKUs amplificar.

### 7.2 Lo que x3 le pide a la arquitectura

- **Throughput operacional**: APScheduler in-memory no aguanta 3,000 ventas/mes. Cola persistida (DT-004 cerrada en Capa 0) es prerequisito.
- **Inventory awareness en tiempo real**: stock-out predictor que detecta cuándo un SKU se agota antes y avisa a procurement. Nuevo evento `inventory.stockout.predicted` en bus.
- **Pricing agility**: cada SKU activo recibe sugerencia diaria. Plano 1 ejecuta automático dentro de envelope.
- **Audience scaling**: Media Buyer rota lookalikes nuevos constantemente, alimentado por Account intel.
- **Quality enforcement**: Compliance Officer monitorea ROG-W4/W5/W6/W7 en tiempo real con alertas de desviación.
- **Portfolio velocity**: Portfolio agent emite weekly brief de SKUs nuevos a sourcear.
- **CGO empoderado**: aprobaciones Plano 2 con autonomía liberan al CEO del bottleneck.

### 7.3 Métricas de éxito

A 3 meses post-Capa 5:
- Ventas/mes WhatsApp: ≥1,000 (vs baseline pre-ARGOS)
- F6 conversion ≥12%
- Cero violaciones de ROG-W (opt-in, cap frecuencia, outcome registration)
- SOV en categorías core ≥15% en MELI Ads + ≥20% en Meta
- Time-to-sale WhatsApp P50 ≤4 minutos
- Top 5 SKUs propuestos por Portfolio agent sourceados y rotando

A 12 meses post-Capa 5:
- Ventas/mes WhatsApp: ≥5,000
- Mind share medible (encuesta a clientes RODDOS): "le pregunto a RODDOS por WhatsApp" ≥50% del top-of-mind para repuestos
- Crédito Rodante con bypass: tiempo aprobación P50 ≤45 seg
- Multi-tenant comercial: primer cliente externo onboardeado (Phase 9 abierta)

---

## 8. Riesgos y mitigaciones

### 8.1 Riesgo arquitectónico · pass-through al Score Engine externo

Si `roddos-scoring` cambia el schema sin aviso o cae en producción, ARGOS rompe el flujo crediticio. Mitigación: contrato canónico versionado + test CI semanal + política de degradación documentada en sección 3.3.

### 8.2 Riesgo regulatorio · Meta 2026 enforcement de WhatsApp

Si una sola conversación viola opt-in (ROG-W1) o frecuencia (ROG-W5) o falta outcome (ROG-W7), Meta puede suspender la WABA. Mitigación: Compliance Officer enforza ROG-W en código desde Capa 0, opt-in registry obligatorio antes de outbound proactivo, monitoreo en tiempo real de cap de frecuencia.

### 8.3 Riesgo competitivo · MELI responde

MELI tiene recursos para reaccionar si detecta un challenger serio en una categoría. Mitigación: moats 3 (memoria) y 7 (aprendizaje) son estructurales y no replicables vía features. La ventana de 18 meses se gana con velocidad de captura, no con superioridad técnica que MELI pueda copiar.

### 8.4 Riesgo de governance · CGO + CEO desalineados

Modelo de información idéntica + approval por planos solo funciona si ambos roles operan con mismos criterios. Mitigación: revisión semanal CEO/CGO de approvals ejecutadas + audit_log con accountability mutua + recalibración mensual del envelope Plano 1.

### 8.5 Riesgo operacional · capacidad de ejecución del equipo SISMO

Sin los 4 endpoints de escritura ARGOS → SISMO operativos, Capa 1 queda en el aire. Mitigación: kick-off con equipo SISMO antes de empezar Capa 0, dependencia explícita en cronograma, plan B de "facturación manual asistida" si SISMO se demora >2 semanas vs su milestone.

---

## 9. Lo que ARGOS NO es (actualizado en 2.1)

- No es CRM (eso es HubSpot)
- No es ERP completo (eso es SISMO V2)
- No es sistema contable
- **No es sistema de cobranza · ni dispara ni procesa · cobranza vive íntegra en SISMO** (corrección 2.1)
- No es herramienta de creatividad (no genera diseños ni copy de campañas; sí sugiere qué SKUs amplificar)
- No es proveedor de tráfico (optimiza pauta, no garantiza resultados)
- No es reemplazo del Score Engine · es pass-through vía API del repo `roddos-scoring`

---

## 10. Próximos pasos formales

1. CEO aprueba esta Visión 2.1 (commit a `docs/VISION_2_1.md`).
2. CEO aprueba CLAUDE.md actualizado con ROGs reescritas + sección 8 con CGO + sección 9 con corrección cobranza.
3. CEO inicia kick-off con equipo SISMO para los 4 endpoints de escritura.
4. CEO arranca Wava onboarding (si no se ha iniciado) y confirmación Mercately WABA.
5. Phase 2.5 abre formalmente con `.planning/phase_2.5_prompt.md`.
6. Bitácora `docs/claude/phase_2.5_alineacion.md` se inicializa vacía.
7. Claude Code lee CLAUDE.md actualizado + canónicas + este documento + el prompt de Phase 2.5 ANTES de codear.

---

## 11. Cierre

ARGOS Visión 2.1 cambia el centro de gravedad de "construir un sistema de inteligencia comercial con WhatsApp" a "construir el venue que desplaza a MELI en repuestos moto en 18 meses". Esa diferencia no es retórica. Reordena la arquitectura (de 11 a 14 componentes), el cronograma (~26 semanas a operación completa), la governance (output unificado CEO+CGO con planos de approval diferenciados), y el criterio de éxito (mind share + share of voice + retention, no solo ventas).

Lo que se preserva intacto: el ADN moto como puerta de entrada, F3 ⭐ y F6 ⭐ como motor de revenue recurrente, el bus append-only y los principios arquitectónicos, la metodología de SISMO V2 que viene funcionando bien, las ROGs como muro de carga inamovible.

Lo que se ajusta: el Score Engine es pass-through (no clon), F5 cobranza queda en SISMO, el output es bilateral CEO/CGO, los 3 componentes nuevos extienden el motor de inteligencia para soportar la tesis competitiva, y el cronograma se extiende para honrar la robustez que la ambición exige.

La tesis sigue siendo recurrente: convertir cada moto vendida en 5 años de repuestos. Lo que cambia es que esos 5 años se construyen siendo el venue donde el cliente regresa por reflejo, no por opción comparada con MELI. Esa es la apuesta, y ARGOS es la herramienta exacta para ejecutarla.

— Visión 2.1 · 29 de abril de 2026
