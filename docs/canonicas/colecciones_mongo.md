# docs/canonicas/colecciones_mongo.md

Schemas de cada colección MongoDB en el cluster argos-prod.

> **Auditado en Phase 2.5 · Build 2.5.1 (2026-04-29)**: cada colección marcada con su estado real.
> Leyenda: ✅ Implementada · 🟡 Spec pendiente · ⚠️ Cambiada por pivote · ⛔ Movida fuera de ARGOS

| Colección | Estado | Phase / Capa |
|-----------|--------|--------------|
| `workspaces` | ✅ Implementada | Phase 0 |
| `users` | ✅ Implementada · CGO role nativo agregado en Build 2.5.5 (ROG-G1) · seed condicional con CGO_EMAIL/CGO_PASSWORD_HASH/CGO_WORKSPACE_ID | Phase 0 + 2.5 |
| `contacts` | ✅ Implementada (Build 2.5.3 · cierra ROG-W1 preventivo) · 4 índices + 4 endpoints + helper `can_send_proactive` | Phase 2.5 |
| `conversations` | 🟡 Spec · construir Capa 1 | Phase 3 / Capa 1 |
| `messages` | 🟡 Spec · construir Capa 1 | Phase 3 / Capa 1 |
| `scoring_solicitudes` | ⚠️ Cambiada · NO vive en cluster ARGOS · `ScoreReader` lee read-only del cluster compartido | Phase 2 (pivote) |
| `products_catalog` | ✅ Implementada | Phase 1 |
| `products_history` | ✅ Implementada | Phase 1 |
| `ads_library` | ✅ Implementada | Phase 1 (Build 2.1) |
| `social_accounts` | ✅ Implementada | Phase 1 (Build 2.3) |
| `social_posts` | ✅ Implementada | Phase 1 (Build 2.3) |
| `keywords` | ✅ Implementada | Phase 1 |
| `briefings` | ✅ Implementada | Phase 1 (Build 3.1) |
| `recommendations` | ✅ Implementada + extensión Phase 2.5 (Build 2.5.5: `approval_required_role` enruta cola CEO/CGO · ROG-G2) | Phase 1 + 2.5 |
| `sismo_inventory` | ✅ Implementada | Phase 1 (Build 4.1) |
| `sismo_sales_daily` | ✅ Implementada | Phase 1 (Build 4.2) |
| `categories` | ✅ Implementada | Phase 1 (Build config) |
| `discovery_suggestions` | ✅ Implementada | Phase 1 (Build config) |
| `watch_queries` | ✅ Implementada | Phase 1 (Build 1.1) |
| `campaigns` | 🟡 Spec · construir Capa 5 | Phase 8 / Capa 5 |
| `cobros` | ⛔ Obsoleta · cobranza vive en SISMO V2 (Visión 2.1 sec 4.7) | — |
| `argos_events` | ✅ Implementada | Phase 0 |
| `agent_memory` | ✅ Implementada | Phase 1 (memoria largo plazo) |
| `agent_sessions` | 🟡 Spec · construir cuando WhatsApp Agent lo requiera | Phase 3 / Capa 1 |
| `audit_log` | ✅ Indices + writers implementados (Build 2.5.2 cierra ROG-A12) · campo `actor_role` añadido para ROG-G3 | Phase 0 + 2.5 |
| `apscheduler_jobs` | ✅ Implementada (Build 2.5.7 · cierra DT-004) · MongoDBJobStore de APScheduler · jobs sobreviven restart de proceso | Phase 2.5 |
| `compliance_envelope` | ✅ Implementada (Build 2.5.4 · cierra ROG-A2 + ROG-A10) · 8 envelopes default sembrados + 3 endpoints + agente ComplianceOfficer | Phase 2.5 |
| `mercately_polling_state` | ✅ Implementada (Build 3.1 · Capa 1) · last_seen per-phone para inbound poller Mercately | Phase 3 / Capa 1 |
| `competitor_profiles` | 🟡 Spec · construir Capa 4 (Account intel agent) | Capa 4 |
| `portfolio_suggestions` | 🟡 Spec · construir Capa 4 (Portfolio agent) | Capa 4 |
| `sku_canonical_aliases` | 🟡 Spec · construir Capa 4 (SKU canonicalizer) | Capa 4 |
| `pricing_suggestions` | 🟡 Spec · construir Capa 5 (Pricing engine) | Capa 5 |
| `notifications_dispatch_log` | 🟡 Spec opcional · alternativa a metadata mutation en argos_events (Build 2.5.9) | Phase 2.5 |
| `deuda_tecnica` | ⚠️ Vive como markdown en `docs/claude/deuda_tecnica.md`, no como collection | — |
| `system_health` | ✅ Implementada | Phase 0 |

Reglas universales:
- Toda colección incluye `workspace_id: string` (ROG-A3) e índice por workspace_id
- Toda colección incluye `created_at: datetime UTC` e índice por created_at
- Cualquier campo PII de terceros se redacta o se omite según ROG-A9 y ROG-W8
- Cualquier cambio de schema es bump de versión + migración documentada en docs/claude/

## Colección: workspaces

| Campo | Tipo | Notas |
|-------|------|-------|
| _id | ObjectId | |
| workspace_id | string unique | Identificador externo (ej: 'RODDOS') |
| name | string | Nombre comercial |
| verticals | array of string | ['REPUESTOS-MOTOS', 'MOTOS'] |
| settings | object | Configuración por workspace |
| created_at | datetime | |

Índices: workspace_id (unique)

## Colección: users

| Campo | Tipo | Notas |
|-------|------|-------|
| _id | ObjectId | |
| workspace_id | string | FK |
| email | string | unique por workspace · se persiste en lowercase |
| password_hash | string | bcrypt (cost 12) · ver nota |
| roles | array of string | ['ceo', 'analista', 'sistema', 'cliente'] · ver nota |
| created_at | datetime | |

Índices: (workspace_id, email) unique

**Nota sobre `password_hash`:** se usa **bcrypt** directo (librería `bcrypt` >=4.1) en vez de Argon2. Razón: `passlib` 1.7.4 tiene incompatibilidad conocida con `bcrypt` 4.x (requiere pinear `bcrypt==4.0.1`) y mantener passlib agrega una dependencia frágil sin ganancia criptográfica relevante para el threat model de ARGOS (hashes nunca expuestos · Atlas con acceso restringido por IP allow-list). Si en el futuro hay requisito FIPS/compliance que fuerce Argon2, migrar con bump de schema versión y rehash progresivo en login.

**Nota sobre `roles`:** se persiste como array para permitir RBAC futuro, pero el JWT actual lleva un único campo `role` (string). `MongoUserStore` toma `roles[0]` como rol activo en el token. Cuando se requiera que un mismo usuario opere con múltiples roles simultáneos (ej: CEO que también es analista), escalar al CEO y diseñar: (a) cambio de contrato JWT a `roles: [str]` o (b) role-selector en login. Hasta entonces, cada usuario tiene un único rol efectivo.

## Colección: contacts (clientes finales)

| Campo | Tipo | Notas |
|-------|------|-------|
| _id | ObjectId | |
| workspace_id | string | FK |
| sismo_customer_id | string | FK al loanbook de SISMO V2 (puede ser null si no es cliente todavía) |
| phone | string | E.164 (+57...) · unique por workspace |
| email | string | opcional |
| nombre_completo | string | de KYC |
| tipo_documento | enum | CC/CE/Pasaporte |
| numero_documento | string | encrypted at-rest |
| fecha_nacimiento | date | |
| genero | enum | M/F/Otro |
| ciudad | string | |
| direccion | string | encrypted at-rest |
| ocupacion_tipo | enum | empleado/independiente/delivery/mototaxi |
| ocupacion_plataforma | string | si delivery: Rappi/DiDi/etc. |
| moto_modelo | string | modelo de moto del cliente (TVS Raider 125, etc.) |
| moto_anio | int | |
| es_cliente_roddos | bool | true si tiene crédito activo o histórico en SISMO |
| score_comportamental | enum | A+/A/B/C/D/E (de loanbook SISMO si aplica) |
| **(actualizado Build 2.5.3 · ROG-W1)** | | El opt-in pasa a estructura nested anidada para poder distinguir marketing vs utility (Meta) y mantener history append-only de cada cambio. |
| phone_number | string E.164 | unique por workspace · reemplaza `phone` legacy |
| opt_in_marketing | object | `{status: opted_in/opted_out/pending, captured_at, channel, consent_text_version, captured_by, history: []}` |
| opt_in_utility | object | misma estructura que `opt_in_marketing` · independiente |
| last_message_at | datetime nullable | actualizado por WhatsApp Agent (Phase 3+) |
| created_at | datetime | |
| updated_at | datetime | |

Índices (Build 2.5.3):
- `(workspace_id, phone_number)` **unique** — `workspace_phone_unique`
- `(workspace_id, opt_in_marketing.status)` — `workspace_opt_in_marketing_status` (driver de outbound campaigns)
- `(workspace_id, opt_in_utility.status)` — `workspace_opt_in_utility_status`
- `(workspace_id, last_message_at desc)` — `workspace_last_message_desc` (recent activity)

**Endpoints (Build 2.5.3):**
- `POST /api/v1/contacts/{phone_number}/opt-in` · upsert con audit trail
- `POST /api/v1/contacts/{phone_number}/opt-out` · cambia status preservando history
- `GET  /api/v1/contacts/{phone_number}/opt-status` · lectura (incluye history)
- `GET  /api/v1/contacts` · listado paginado con filtros opt-in

**Gate de outbound (ROG-W1 enforcement):** TODO mensaje proactivo Phase 3+ debe llamar
`argos.services.opt_in.can_send_proactive(db, workspace_id, phone, type)` antes de enviar.
Si retorna `(False, reason)`, el envío se bloquea y se loggea.

## Colección: conversations

| Campo | Tipo | Notas |
|-------|------|-------|
| _id | ObjectId | |
| workspace_id | string | |
| contact_id | ObjectId | FK contacts |
| started_at | datetime | |
| ended_at | datetime | null mientras activa |
| messages_count | int | |
| intent_classification | enum | cotizar_moto/cotizar_repuesto/pago_cuota/soporte/otro |
| outcome | enum | vendio/no_vendio/handoff_humano/abandono · ROG-W7 |
| value_usd | float | venta total atribuida si outcome = vendio |
| handoff_reason | string | si aplicó |
| ai_messages | int | mensajes generados por WhatsApp Agent |
| human_messages | int | mensajes del operador humano post-handoff |

Índices: (workspace_id, contact_id, started_at) · (workspace_id, outcome) · (workspace_id, intent_classification)

## Colección: messages

| Campo | Tipo | Notas |
|-------|------|-------|
| _id | ObjectId | |
| workspace_id | string | |
| conversation_id | ObjectId | FK conversations |
| direction | enum | inbound/outbound |
| sender | enum | client/whatsapp_agent/operator_human |
| message_type | enum | text/image/audio/document/template/flow |
| content | string | texto o caption |
| media_url | string | si aplica |
| transcription | string | si message_type = audio (Whisper output) |
| vision_analysis | object | si message_type = image (Claude vision output) |
| template_name | string | si outbound y es template aprobado |
| cost_usd | float | costo del mensaje según pricing Meta |
| timestamp_utc | datetime | |

Índices: (workspace_id, conversation_id, timestamp_utc)

## Colección: scoring_solicitudes

> **Corrección arquitectónica 2026-04-27**: esta colección NO vive en el cluster
> de ARGOS (`MONGODB_URI`). Vive en el cluster Atlas compartido con RODDOS-web,
> apuntado por `RODDOS_MONGODB_URI` · base `roddos_comercial` · escrita por el
> Score Engine externo (repo independiente de Iván). ARGOS solo LEE vía
> `ScoreReader` con scope read-only (ROG-A11). El POST /api/v1/score/evaluate
> es pass-through HTTP al Score Engine de Iván — ARGOS no toca esta colección
> en escritura.

Schema fiel al Build 20 de RODDOS, con marca de origen `argos`.

| Campo | Tipo | Notas |
|-------|------|-------|
| _id | ObjectId | |
| workspace_id | string | |
| solicitud_id | string unique | Formato: SCR-ARGOS-2026-XXXX (diferenciado del web: SCR-WEB-2026-XXXX) |
| origen | enum | argos (canal WhatsApp) · web (canal roddos.com) — ROG-S1 |
| contact_id | ObjectId | FK contacts |
| estado | enum | pendiente/en_evaluacion/aprobado/rechazado/revision_manual |
| **Datos personales** | | (heredados del Build 20) |
| nombre_completo, email, telefono, fecha_nacimiento, genero, tipo_documento, numero_documento, lugar_expedicion, lugar_nacimiento | varios | encrypted PII |
| **Residencia** | | |
| pais, departamento, ciudad, direccion, zona | varios | |
| **Actividad económica** | | |
| tipo_empleo, plataforma_delivery, rango_salarial, gastos_mensuales, tiempo_actividad_meses, uso_moto | varios | |
| **Producto** | | |
| producto | enum | credito_moto/credito_repuestos/ambos |
| monto_solicitado | float | |
| **Referencia** | | |
| referencia_nombre, referencia_telefono, referencia_direccion | varios | |
| **Resultados de partners** | | |
| auco_validacion | object | {estado, score_biometrico, timestamp} |
| palenca_data | object | si delivery/mototaxi |
| riskseal_data | object | {digital_score, fraud_flag, data_points_count} — NUEVO en ARGOS |
| documentos | array | [{tipo, claude_analysis, ingreso_verificado, gastos_verificados}] |
| **Score y decisión** | | |
| score_modelo | float | output XGBoost 0-1 |
| score_claude | float | ajuste cualitativo -0.15 a +0.15 |
| score_final | int | 0-1000 |
| categoria_riesgo | enum | muy_bajo/bajo/medio/alto/muy_alto |
| decision | enum | aprobado/rechazado/revision_manual |
| monto_aprobado | float | null si rechazado |
| narrativa_decision | string | generada por Claude (auditable · ROG-S4) |
| reglas_aplicadas | enum | credito_moto/credito_repuestos |
| tiempo_evaluacion_seg | int | objetivo < 300 (5 min) |
| modelo_version_hash | string | hash del XGBoost activo · ROG-S5 |
| **Timestamps** | | |
| creado_en | datetime | |
| evaluado_en | datetime | null mientras pendiente |
| notificado_en | datetime | timestamp de envío WhatsApp |

Índices: (workspace_id, solicitud_id) unique · (workspace_id, origen, creado_en) · (workspace_id, estado) · (workspace_id, contact_id)

## Colección: products_catalog (repuestos detectados en marketplaces)

| Campo | Tipo | Notas |
|-------|------|-------|
| _id | ObjectId | |
| workspace_id | string | |
| sku_normalizado | string | SKU canónico interno |
| source | enum | meli/fb_mp/competitor_site |
| source_id | string | ID en la fuente |
| nombre | string | |
| categoria | string | jerárquica: 'repuestos.frenos.pastillas' |
| compatible_motos | array | ['TVS Raider 125 2020-2024', 'Pulsar NS 200 2018-2024'] |
| precio_actual | float | COP |
| stock_disponible | int | |
| seller_id | string | hash si no es público |
| imagen_url | string | |
| created_at | datetime | |
| updated_at | datetime | |
| embedded_at | datetime nullable | (Build 3.2) timestamp del último upsert en Qdrant `products_embeddings` · null si pending |

Índices: `(workspace_id, sku_normalizado)` · `(workspace_id, source, source_id)` **unique** · `(workspace_id, categoria)` · `(workspace_id, updated_at)`

**Nota sobre `sku_normalizado` (Build 1.0):** convención actual es `{source}:{source_id}` (ej. `meli:MCO-12345`). Build 1.1 introducirá Haiku para agrupar variantes del mismo producto bajo un SKU canónico real (ej. `repuesto.freno.pastilla.tvs-raider-125`). Hasta entonces, `sku_normalizado` actúa como FK estable por-item, no como identificador semántico.

**Nota sobre `categoria` (Build 1.0):** queda **vacía** (`""`) en Build 1.0 · Build 1.1 (Haiku categorizer) genera la jerarquía `repuestos.frenos.pastillas`. El campo auxiliar `categoria_meli_id` persiste el `category_id` crudo que devuelve MELI para referencia futura.

## Colección: products_history

Series temporales de precios y stock.

| Campo | Tipo | Notas |
|-------|------|-------|
| _id | ObjectId | |
| workspace_id | string | |
| product_id | ObjectId | FK products_catalog |
| timestamp | datetime | |
| precio | float | |
| stock | int | |
| source | enum | |

Índices: (workspace_id, product_id, timestamp)

## Colección: ads_library

Schema **canónico Build 2.1** · ads detectados en Meta Ad Library (futuro: Google Transparency, TikTok).

| Campo | Tipo | Notas |
|-------|------|-------|
| _id | ObjectId | |
| workspace_id | string | FK · ROG-A3 |
| plataforma | enum | `meta` / `google` / `tiktok` |
| ad_id_externo | string | ID del ad en la plataforma · ej. `ad_archive_id` de FB Ad Library |
| anunciante | string | Nombre de la página/marca (≤200 chars) |
| copy_texto | string | Copy completo del ad (≤2000 chars) |
| copy_titulo | string | Título / headline (≤300 chars) |
| url_landing | string | Destino del CTA · permalink al landing del anunciante |
| fecha_inicio | datetime | `ad_delivery_start_time` parsed |
| fecha_fin | datetime nullable | `ad_delivery_stop_time` · null si activo |
| durabilidad_dias | int | calculado · `(fecha_fin or now) - fecha_inicio` |
| formato | enum | `image` / `video` / `carousel` / `unknown` |
| activo | bool | True si `fecha_fin` es null (Meta) · True si `fecha_fin` < 7 días atrás (Google · heurística por lag de transparency reporting) |
| fuente_query | string | watch_query que disparó el último scrape |
| keywords_pautadas | array of string | (Build 2.2 · Google Ads) queries del workspace que han detectado este ad · array set acumulativo via `$addToSet` |
| primera_deteccion | datetime | timestamp de upsert inicial · `$setOnInsert` |
| ultima_deteccion | datetime | timestamp del último scrape donde aparece |
| created_at, updated_at | datetime | |
| embedded_at | datetime nullable | (Build 3.2) timestamp del último upsert en Qdrant `ads_embeddings` · null si pending |
| competitor_id | string | (futuro · cuando se cree colección `competitors`) |
| sku_referenciado | string | (futuro · si Strategist lo asocia) |
| estimado_spend | float | si SerpAPI lo da |

Índices: (workspace_id, platform, ad_id_externo) unique · (workspace_id, competitor_id) · (workspace_id, activo_actualmente)

## Colección: social_accounts (Build 2.3)

Schema canónico Build 2.3 · cuentas IG/TikTok detectadas por SocialAgent vía TikHub.

| Campo | Tipo | Notas |
|-------|------|-------|
| _id | ObjectId | |
| workspace_id | string | FK · ROG-A3 |
| plataforma | enum | `ig` / `tiktok` / `youtube` (futuro) |
| username | string | handle/identifier (sin `@`) |
| seguidores | int | follower count |
| engagement_rate | float | avg_likes / followers × 100 · cap a 100 |
| descripcion | string | bio/signature (≤500 chars) |
| url_perfil | string | share_url o profile_url |
| relevancia_score | float | log10(seguidores)*10 + engagement*2 · cap 100 |
| sec_uid | string | TikTok-only · necesario para fetch posts |
| fuente_query | string | watch_query que detectó la cuenta |
| ultima_metricas_at | datetime | |
| created_at, updated_at | datetime | |

Índices: `(workspace_id, plataforma, username)` **unique** · `(workspace_id, relevancia_score desc)` · `(workspace_id, seguidores desc)`

## Colección: social_posts (Build 2.3)

Posts virales (≥ 50K vistas) detectados por SocialAgent.

| Campo | Tipo | Notas |
|-------|------|-------|
| _id | ObjectId | |
| workspace_id | string | FK · ROG-A3 |
| plataforma | enum | `ig` / `tiktok` |
| username | string | denormalizado · evita join cuando se renderiza |
| post_external_id | string | ID del post en la plataforma |
| url_post | string | permalink |
| descripcion | string | caption/desc (≤1000 chars) |
| vistas | int | play_count o video_view_count |
| likes | int | digg_count o like_count |
| comentarios | int | comment_count |
| hashtags | array of string | extraídos de la descripción · max 30 · lowercase deduped |
| fecha_publicacion | datetime nullable | create_time parseado |
| viral_flag | bool | True (solo se persisten los virales) |
| created_at, updated_at | datetime | |

Índices: `(workspace_id, post_external_id)` **unique** · `(workspace_id, vistas desc)` · `(workspace_id, fecha_publicacion desc)`

**Nota Build 2.3**: el FK a `social_accounts` se denormaliza por `username` en vez de `account_id` ObjectId · facilita queries directas y evita lookups en el endpoint frontend. La integridad referencial se mantiene a nivel app (SocialAgent siempre upsert account antes de upsert posts del mismo username).

## Colección: keywords

| Campo | Tipo | Notas |
|-------|------|-------|
| _id | ObjectId | |
| workspace_id | string | |
| keyword | string | |
| search_volume | int | |
| growth_pct_7d | float | |
| growth_pct_30d | float | |
| vertical | string | |
| spike_detected | bool | |
| updated_at | datetime | |

## Colección: briefings (Build 3.1)

Morning Briefings generados por StrategistAgent + persistidos por ExecutiveAgent. Una entrada por (workspace_id, fecha).

| Campo | Tipo | Notas |
|-------|------|-------|
| _id | ObjectId | |
| workspace_id | string | FK · ROG-A3 |
| fecha | string | YYYY-MM-DD UTC · clave de idempotencia con workspace_id |
| mercado_24h | object | `{nuevos_skus: int, bajas_precio: int, nuevas_promos: int}` |
| acciones_del_dia | array of object | Máx 3 · `{accion, justificacion, impacto_esperado, prioridad: Alta/Media/Baja}` |
| estado_mercado | string | resumen ejecutivo del día (≤1000 chars) |
| modelo_usado | string | versión pineada del modelo (ej. `claude-sonnet-4-6-20260301`) |
| tokens_input | int | input tokens consumidos en la llamada |
| tokens_output | int | output tokens generados |
| created_at | datetime | `$setOnInsert` · timestamp del primer briefing del día |
| updated_at | datetime | refrescado en re-run del job |

Índices: `(workspace_id, fecha)` **unique** · `(workspace_id, created_at desc)`

**Idempotencia**: re-runs del `morning_briefing_job` en el mismo día actualizan el documento (no insertan duplicado). El evento `briefing.published` se emite en cada corrida — útil para auditar quién/cuándo se generó.

## Colección: recommendations

| Campo | Tipo | Notas |
|-------|------|-------|
| _id | ObjectId | |
| workspace_id | string | |
| created_at | datetime | |
| type | enum | pricing_change/promo_launch/ad_campaign/inventory_reorder/competitive_response/portfolio_add/portfolio_drop |
| sku_affected | string or array | |
| action_description | string | |
| rationale | string | |
| evidence_refs | array | IDs en products_catalog, ads_library, etc. |
| expected_impact | object | {metric, baseline, target, confidence} |
| actual_impact | object | poblado en T+7 desde SISMO |
| hit_rate_contribution | float | 0.0-1.0 |
| learning | string | reflexión post-mortem del Strategist |
| status | enum | pendiente/aprobada/ejecutada/rechazada/rechazada_compliance/expirada/evaluada |
| approved_by | string | user_id del aprobador |
| approved_at | datetime | |
| executed_at | datetime | |
| priority_score | float | 0.0-1.0 |
| priority | enum | Alta/Media/Baja (texto · refleja `accion.prioridad` del Strategist) |
| shown_in_briefing | array of dates | `$addToSet` en cada briefing que la incluye |
| briefing_id | string | _id del briefing del que se derivó (Build 3.3) |
| accion_index | int | índice 0-based dentro de `acciones_del_dia` (Build 3.3) |
| fecha_briefing | string YYYY-MM-DD | fecha del briefing original |
| evaluated_at | datetime | timestamp de cierre del job de impact evaluation |
| rejected_by | string | nullable |
| rejected_at | datetime | nullable |
| rejected_reason | string | máx 300 chars |
| updated_at | datetime | |

Índices (Build 3.3):
- `(workspace_id, status, priority_score desc)` — `workspace_status_priority`
- `(workspace_id, created_at desc)` — `workspace_created_desc`
- `(workspace_id, briefing_id, accion_index)` **unique** con `partialFilterExpression: {briefing_id: {$exists: true}}` — `workspace_briefing_accion_unique` (idempotencia del job de persistencia)
- `(workspace_id, executed_at)` con `partialFilterExpression: {executed_at: {$exists: true}}` — `workspace_executed` (driver del impact evaluation job)

**Idempotencia**: `persist_recommendations_from_briefing` upsert por `(workspace_id, briefing_id, accion_index)`. Re-runs del briefing del mismo día actualizan campos mutables (`action_description`, `rationale`, `priority`) pero NO crean duplicados ni resetean `created_at` (`$setOnInsert`). `shown_in_briefing` se acumula con `$addToSet`.

**Lifecycle del status**:
- `pendiente` → estado inicial al persistir desde briefing
- `aprobada` → CEO aprueba vía `POST /api/v1/recommendations/{id}/approve` (sólo desde `pendiente`)
- `rechazada` → CEO rechaza vía `POST /{id}/reject` con `reason` opcional
- `ejecutada` → manual (o futuro Media Buyer) marca `executed_at`
- `evaluada` → impact evaluation job (cron 07:00 UTC) lee `status=ejecutada` con `executed_at` ≥ 7d, calcula `hit_rate_contribution`, genera `learning` con Sonnet 4.6, persiste `actual_impact` + `evaluated_at`

## Colección: sismo_inventory (Build 4.1 · snapshot read-only)

Snapshot diario del inventario leído de SISMO V2 vía `SismoAgent.sync_sismo_inventory_job` (cron 6h). Idempotente por `(workspace_id, sku, fecha_sync_date)`.

| Campo | Tipo | Notas |
|-------|------|-------|
| _id | ObjectId | |
| workspace_id | string | ROG-A3 |
| sku | string | clave canónica del repuesto en SISMO |
| nombre | string | descripción ≤200 chars |
| stock | int | unidades en bodega al momento del sync |
| precio | float | precio de venta COP |
| costo | float | costo unitario COP (para `valor_inventario` agregado) |
| dias_inventario | int | días sin rotación según SISMO |
| is_slow_mover | bool | `True` si `dias_inventario >= 45` (umbral hardcoded · ver `SLOW_MOVER_DAYS_THRESHOLD`) |
| fecha_sync_date | string YYYY-MM-DD | clave del snapshot · permite múltiples días en histórico |
| fecha_sync | datetime UTC | timestamp exacto del sync |
| created_at | datetime | `$setOnInsert` |
| updated_at | datetime | refrescado en re-runs del mismo día |

Índices (Build 4.1):
- `(workspace_id, sku, fecha_sync_date)` **unique** — `workspace_sku_fecha_unique` (idempotencia del sync job)
- `(workspace_id, fecha_sync desc)` — `workspace_fecha_sync_desc` (driver del endpoint /sismo/inventory)
- `(workspace_id, is_slow_mover, dias_inventario desc)` — `workspace_slow_movers` (filtro `type=slow_movers`)

**Skip silencioso**: si `SISMO_API_URL`/`SISMO_API_KEY` no están seteadas, `sync_sismo_inventory_job` no toca Mongo y devuelve `SyncStats(enabled=False)`. ROG-A11: la key debe ser scope read-only.

**Consumido por**: `Strategist.gather_signals` (Build 4.1) lee el último snapshot por workspace y enriquece el briefing con `inventory_summary` (totales + valor inventario) y top 10 `slow_movers` para que el LLM proponga acciones de liquidación.

## Colección: sismo_sales_daily (Build 4.2 · ventas diarias por SKU)

Snapshot diario de ventas leído de SISMO V2 vía `sync_sismo_sales_daily_job` (cron 01:00 UTC). Una fila por (date, sku). Alimenta el impact tracker para evaluar `pricing_change`/`promo_launch` con números reales.

| Campo | Tipo | Notas |
|-------|------|-------|
| _id | ObjectId | |
| workspace_id | string | ROG-A3 |
| date | string YYYY-MM-DD | día de venta · clave temporal |
| sku | string | SKU canónico de SISMO |
| units_sold | int | unidades vendidas en el día |
| revenue | float | revenue COP del día para ese SKU |
| channel | string | tienda/whatsapp/web/n.a. (≤50 chars) |
| fecha_sync | datetime UTC | timestamp del sync |
| created_at | datetime | `$setOnInsert` |
| updated_at | datetime | refrescado en re-runs |

Índices (Build 4.2):
- `(workspace_id, date, sku)` **unique** — `workspace_date_sku_unique` (idempotencia del job)
- `(workspace_id, date desc)` — `workspace_date_desc` (driver del endpoint /sismo/sales · default último día)
- `(workspace_id, sku, date desc)` — `workspace_sku_date_desc` (queries por SKU en ventana temporal · usado por impact tracker)

**Skip silencioso**: si `SISMO_API_URL`/`SISMO_API_KEY` vacíos → `SalesSyncStats(enabled=False)`, no toca Mongo.

**Consumido por**:
- `Strategist.impact._aggregate_real_sales_window` para poblar `actual_impact` con `units_sold + revenue_cop` reales en recomendaciones de tipo `pricing_change` o `promo_launch` (ventana T..T+7 desde `executed_at`).
- Endpoint `GET /api/v1/sismo/sales?date=YYYY-MM-DD&sku=optional` para la vista `/sismo > Ventas`.

## Colección: categories (Build config · catálogo de verticales)

| Campo | Tipo | Notas |
|-------|------|-------|
| _id | ObjectId | |
| workspace_id | string | ROG-A3 |
| slug | string | clave canónica · ej. `repuestos_moto`, `accesorios_moto` |
| label | string | nombre legible |
| active | bool | si está `true`, `discovery_job` corre los 3 métodos para esta categoría |
| created_at | datetime | |
| updated_at | datetime | |

Índices: `(workspace_id, slug)` **unique** · `(workspace_id, active)`

**Seed**: 4 categorías defaults · `repuestos_moto` (active=True), `accesorios_moto/motos/aceites_lubricantes` (active=False).

**Endpoints**: `GET /api/v1/config/categories` · `PATCH /api/v1/config/categories/{slug}` · `POST /api/v1/config/categories/request` (emite `config.category.requested`).

## Colección: discovery_suggestions (Build config · auto-discovery)

Sugerencias generadas por `DiscoveryAgent.run_discovery_job` (cron 06:00 UTC) · upsert idempotente por `(workspace, category, term, signal_type, date)`.

| Campo | Tipo | Notas |
|-------|------|-------|
| _id | ObjectId | |
| workspace_id | string | |
| category | string | slug de `categories` |
| term | string | candidato a watch_query |
| signal_type | enum | `trending` / `rising` / `liquidating` / `disappearing` |
| confidence | float 0.0-1.0 | mayor = más fuerte la señal |
| evidence | object | `{metric, value, delta_pct}` · texto natural en frontend |
| date | string YYYY-MM-DD | día del run · clave del unique compound |
| status | enum | `pending` / `accepted` / `dismissed` |
| accepted_by, accepted_at | string/datetime | poblados al aceptar (crea watch_query origin='suggested') |
| dismissed_by, dismissed_at, dismiss_reason | string/datetime/string | poblados al descartar |
| created_at, updated_at | datetime | |

Índices:
- `(workspace_id, category, term, signal_type, date)` **unique** — `workspace_cat_term_signal_date_unique`
- `(workspace_id, status, confidence desc)` — `workspace_status_confidence`
- `(workspace_id, date desc)` — `workspace_date_desc`

**Consumido por**: `Strategist.gather_signals` lee top 3 con `status=pending` para inyectar en el contexto del Morning Briefing · permite que el LLM mencione "ARGOS detectó N términos emergentes que no estás monitoreando".

## Extensión `watch_queries` (Build config · panel de inteligencia)

Campos nuevos sobre el schema Build 1.1:

| Campo | Tipo | Notas |
|-------|------|-------|
| origin | enum | `manual` / `suggested` / `auto_discovered` · cómo entró al sistema. Legacy docs migran a `manual` |
| category | string \| null | slug de `categories` · null para queries pre-Build config |
| status | enum | `active` / `paused` · alias canónico de `activa: bool` (sync'd) |
| priority | int 1-10 | alias canónico de `prioridad` (sync'd) |
| suggested_from | string | ObjectId de `discovery_suggestions._id` cuando `origin=suggested` |

**Migración**: `ensure_indexes` corre backfill que setea `origin/status/priority/category` con defaults para docs legacy. Idempotente.

**Decisión arquitectónica**: el campo `source` (existente Build 1.1 con valores `meli/fb_marketplace/all`) se mantiene · NO se reusa para el origen del query como pedía el spec original. El nuevo concepto se llama `origin` para evitar romper Scout.

## Colección: campaigns

| Campo | Tipo | Notas |
|-------|------|-------|
| _id | ObjectId | |
| workspace_id | string | |
| recommendation_id | ObjectId | FK |
| platform | enum | meta/google |
| external_id | string | ID en la plataforma destino |
| budget_total | float | COP |
| spending_actual | float | COP |
| status | enum | active/paused/completed |
| metrics | object | {impressions, clicks, conversions, ctr, cpc, roas} |
| created_at | datetime | |

## Colección: cobros

| Campo | Tipo | Notas |
|-------|------|-------|
| _id | ObjectId | |
| workspace_id | string | |
| customer_id | ObjectId | FK contacts |
| credito_id | string | FK loanbook SISMO |
| cuota_numero | int | 1 a 39/52/78 |
| monto | float | COP |
| fecha_vencimiento | date | |
| wava_link_id | string | |
| wava_link_url | string | |
| estado | enum | pendiente/notificado/pagado/vencido/escalado |
| pagado_en | datetime | |
| metodo_pago | enum | nequi/daviplata/pse/tarjeta |
| transaction_id_wava | string | |
| recordatorios_enviados | int | |
| ultimo_recordatorio_at | datetime | |
| created_at | datetime | |

Índices: (workspace_id, customer_id, estado) · (workspace_id, fecha_vencimiento, estado)

## Colección: argos_events (bus append-only · ROG-A6)

| Campo | Tipo | Notas |
|-------|------|-------|
| _id | ObjectId | |
| event_id | string unique | ULID |
| event_type | string | dot.notation |
| version | string | semver |
| workspace_id | string | |
| timestamp_utc | datetime | |
| producer | string | |
| correlation_id | string | |
| causation_id | string | nullable |
| payload | object | |
| metadata | object | |

Índices: event_id unique · (workspace_id, event_type, timestamp_utc) · correlation_id

Política: NUNCA UPDATE · NUNCA DELETE · solo INSERT

## Colección: watch_queries (Build 1.1)

Queries semilla que el Scout itera en cada tick (cada 6h en prod). Schema:

| Campo | Tipo | Notas |
|-------|------|-------|
| _id | ObjectId | |
| workspace_id | string | FK · ROG-A3 |
| query | string | texto literal de búsqueda (ej. "aceite moto") |
| source | enum | `meli` / `fb_marketplace` / `all` (Scout itera ambas) |
| activa | bool | Scout solo procesa las activas |
| prioridad | int | 1=baja, 5=alta · Scout ordena por prioridad desc |
| created_at | datetime | |

Índices: `(workspace_id, query)` **unique** · `(workspace_id, activa)` · `(workspace_id, source)`

**Operación:**
- Seed inicial inserta 11 queries por workspace nuevo con `$setOnInsert` (no sobrescribe ediciones del CEO)
- Edición vía Mongo directo o endpoints futuros (Build 1.2+ añade PATCH/POST/DELETE)
- Endpoint `GET /api/v1/scout/watch-queries` (rol ceo) lista todas (activas+inactivas) del workspace del usuario

## Colección: agent_memory (memoria de largo plazo por agente)

| Campo | Tipo | Notas |
|-------|------|-------|
| _id | ObjectId | |
| workspace_id | string | |
| agent_name | string | |
| memory_key | string | jerárquico |
| memory_value | object | |
| importance | float | 0.0-1.0 para retrieval ranking |
| created_at | datetime | |
| updated_at | datetime | |

## Colección: agent_sessions (TTL 72h)

Estado conversacional de corta duración. TTL index sobre `expires_at`.

| Campo | Tipo | Notas |
|-------|------|-------|
| _id | ObjectId | |
| workspace_id | string | |
| agent_name | string | |
| session_id | string | |
| state | object | |
| expires_at | datetime | TTL 72h desde última actualización |

## Colección: audit_log

| Campo | Tipo | Notas |
|-------|------|-------|
| _id | ObjectId | |
| workspace_id | string | |
| timestamp_utc | datetime | |
| actor_type | enum | user/system/agent |
| actor_id | string | |
| action | string | |
| resource_type | string | |
| resource_id | string | |
| metadata | object | |
| result | enum | success/failure |
| ip_address | string | si aplica |

Índices: (workspace_id, timestamp_utc) · (workspace_id, actor_id) · (workspace_id, resource_type, resource_id)

## Colección: apscheduler_jobs (Build 2.5.7 · cierra DT-004)

Colección interna de APScheduler · **no leer/escribir directamente desde código de aplicación**.
Gestionada exclusivamente por `apscheduler.jobstores.mongodb.MongoDBJobStore`.
Persiste el estado de los jobs periódicos entre reinicios del proceso en Render.

| Campo | Tipo | Notas |
|-------|------|-------|
| _id | string | job_id (ej. `scout_tick`, `morning_briefing`) |
| next_run_time | datetime | próxima ejecución programada |
| job_state | binary | pickle del objeto Job (scheduler-internal) |

**Configuración:**
- `host`: `MONGODB_URI` (mismo cluster que el resto de ARGOS)
- `collection`: `apscheduler_jobs`
- `coalesce`: True en todos los jobs · si un tick se pierde, solo ejecuta una vez al recuperarse
- `misfire_grace_time`: 60s para jobs daily/6h · 300s para jobs de alta frecuencia (1h, 30min)

**Comportamiento por entorno:**
- `MONGODB_URI` configurado (prod/staging): `MongoDBJobStore` · jobs sobreviven restart
- `MONGODB_URI` vacío (dev sin DB, tests): `MemoryJobStore` · jobs se pierden en restart (aceptable para desarrollo local)

**Nota de implementación (Build 2.5.7)**: los job wrappers de `scheduler.py` ya no reciben
`db: AsyncIOMotorDatabase` como argumento — usan la variable de módulo `_db` en su lugar.
Esto es necesario porque APScheduler serializa los jobs con pickle, y `AsyncIOMotorDatabase` no es picklable.

## Colección: mercately_polling_state (Build 3.1 · Capa 1)

Estado de polling per-phone del inbound poller de Mercately. Persiste el último mensaje procesado por teléfono para evitar reprocesamiento.

| Campo | Tipo | Notas |
|-------|------|-------|
| _id | ObjectId | auto |
| phone | string | 12 dígitos formato 57XXXXXXXXXX |
| workspace_id | string | ROG-A3 |
| last_seen_at | datetime | timestamp del último mensaje inbound procesado |
| created_at | datetime | primera vez que se polleó este phone |
| updated_at | datetime | última actualización |

Índices: (phone, workspace_id) unique

## Colección: deuda_tecnica

| Campo | Tipo | Notas |
|-------|------|-------|
| _id | ObjectId | |
| workspace_id | string | |
| titulo | string | |
| descripcion | string | |
| modulo | string | |
| prioridad | enum | baja/media/alta/critica |
| owner | string | |
| created_at | datetime | |
| resuelto_en | datetime | nullable |
| resuelto_por | string | nullable |

## Colección: system_health

| Campo | Tipo | Notas |
|-------|------|-------|
| _id | ObjectId | |
| timestamp_utc | datetime | |
| component | string | |
| status | enum | healthy/degraded/down |
| details | object | |
| metrics | object | {response_time_ms, error_rate, etc.} |
