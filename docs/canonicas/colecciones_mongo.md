# docs/canonicas/colecciones_mongo.md

Schemas de cada colección MongoDB en el cluster argos-prod.

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
| opt_in_marketing | bool | ROG-W1 |
| opt_in_marketing_at | datetime | timestamp + canal de obtención |
| opt_in_canal | string | 'whatsapp_first_message' / 'web_form' / 'qr_empaque' |
| created_at | datetime | |

Índices: (workspace_id, phone) unique · (workspace_id, sismo_customer_id) · (workspace_id, es_cliente_roddos)

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
