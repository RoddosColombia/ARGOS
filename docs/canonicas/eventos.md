# docs/canonicas/eventos.md

Bus argos_events. Append-only e inmutable (ROG-A6).

## Schema base de todo evento

```json
{
  "event_id": "evt_2026_xxxxxxxxx",          // ULID, único
  "event_type": "score.evaluated",            // dot.notation jerárquico
  "version": "1.0",                           // semver del schema del evento
  "workspace_id": "RODDOS",                   // multi-tenant obligatorio (ROG-A3)
  "timestamp_utc": "2026-04-21T13:50:00Z",    // ISO 8601 UTC
  "producer": "score_engine",                 // qué agente o módulo emitió
  "correlation_id": "conv_abc123",            // para encadenar eventos relacionados
  "causation_id": "evt_2026_yyy",             // qué evento previo lo causó (null si origen)
  "payload": { /* específico al event_type */ },
  "metadata": {
    "model_version": "xgb_v2.1_hash_a1b2",
    "trace_id": "trace_xyz"
  }
}
```

## Catálogo de eventos por dominio

### Dominio: WhatsApp (canal de cliente)

| event_type | Productor | Consumidores | Payload clave |
|------------|-----------|--------------|---------------|
| whatsapp.message.received | mercately_webhook | whatsapp_agent, executive | {phone, contact_id, message_type, content, media_url, conversation_id} |
| whatsapp.message.sent | whatsapp_agent | executive, audit_log | {phone, message_id, template_used, cost_usd, channel} |
| whatsapp.opt_in.granted | whatsapp_agent | compliance_officer, sismo_sync | {phone, contact_id, channel_obtention, timestamp} |
| whatsapp.opt_out.requested | whatsapp_agent | compliance_officer, sismo_sync | {phone, contact_id, reason} |
| whatsapp.handoff.triggered | whatsapp_agent | executive, audit_log | {phone, conversation_id, reason, escalation_level} |
| whatsapp.conversation.closed | whatsapp_agent | strategist, learning | {conversation_id, outcome, duration_seg, messages_count, value_usd} |
| whatsapp.intent.classified | whatsapp_agent | strategist | {phone, intent_type: cotizar_moto/cotizar_repuesto/pago_cuota/soporte/otro, confidence} |

### Dominio: Score Engine (motor de score interno de ARGOS)

| event_type | Productor | Consumidores | Payload clave |
|------------|-----------|--------------|---------------|
| score.solicitud.created | whatsapp_agent | score_engine | {solicitud_id, producto, monto, kyc_data} |
| score.kyc.completed | score_engine | risk_validator | {solicitud_id, kyc_completo: bool, missing_fields} |
| score.partner.queried | score_engine | audit_log | {solicitud_id, partner: auco/palenca/riskseal, resultado, latency_ms} |
| score.hard_rules.evaluated | score_engine | strategist | {solicitud_id, rechazo_inmediato: bool, regla_violada} |
| score.ml.calculated | score_engine | audit_log | {solicitud_id, score_modelo, model_hash, features_used} |
| score.claude.adjusted | score_engine | audit_log | {solicitud_id, ajuste, narrativa, tokens_usados} |
| score.evaluated | score_engine | whatsapp_agent, sismo_sync, dashboard | {solicitud_id, score_final, categoria, decision, monto_aprobado} |
| score.notified | whatsapp_agent | audit_log | {solicitud_id, notification_method: whatsapp, delivered: bool} |

### Dominio: Cobranza (RADAR + Wava)

| event_type | Productor | Consumidores | Payload clave |
|------------|-----------|--------------|---------------|
| cobro.programado | sismo_radar_sync | cobranza_orchestrator | {customer_id, cuota_numero, monto, fecha_vencimiento, credito_id} |
| cobro.link_generated | wava_integration | whatsapp_agent | {customer_id, wava_link, expira_en, monto, metodos: nequi/daviplata} |
| cobro.notificacion.enviada | whatsapp_agent | audit_log | {customer_id, link_id, fecha_envio} |
| cobro.pago.recibido | wava_webhook | sismo_radar_sync, whatsapp_agent | {customer_id, link_id, monto, metodo, transaction_id, timestamp} |
| cobro.pago.confirmado | sismo_radar_sync | whatsapp_agent | {customer_id, cuota_numero, saldo_actualizado} |
| cobro.recordatorio.disparado | cobranza_orchestrator | whatsapp_agent | {customer_id, days_overdue, cuota_numero, intensidad: suave/medio/firme} |
| cobro.morosidad.detectada | cobranza_orchestrator | strategist, executive, sismo_sync | {customer_id, days_overdue, monto_acumulado, accion_sugerida} |

### Dominio: Marketplace e inteligencia

| event_type | Productor | Consumidores | Payload clave |
|------------|-----------|--------------|---------------|
| marketplace.product.detected | scout, marketplace_agent | strategist | {sku_normalizado, source: meli/fb_marketplace, source_id, nombre, categoria, precio_actual, created: bool} |
| marketplace.price.changed | marketplace_agent | strategist, competitors | {sku_normalizado, source, source_id, price_before, price_after, delta_pct} · threshold ≥ 5% |
| scout.product.discarded | scout (classifier Haiku) | strategist (futuro · feedback loop), audit_log | {source, source_id, title, watch_query, reason} · emitido cuando classifier marca relevante=False · permite auditoría de falsos negativos |
| marketplace.competitor.detected | competitors | strategist | {competitor_id, source, sku, precio} |
| competitor.ad.detected | competitors | strategist | {competitor_id, platform: meta/google/tiktok, ad_id, copy, creative_url, durabilidad_dias} · (legacy · ver `competitors.ad.detected` Build 2.1) |
| competitors.ad.detected | competitors_agent | strategist, executive | {plataforma, ad_id_externo, anunciante, copy_titulo, fuente_query, durabilidad_dias, formato} · emitido SOLO en primera detección del ad (re-detecciones en mismo upsert no spamean el bus) |
| competitor.promo.detected | competitors | strategist, executive | {competitor_id, sku, descuento_pct, vigencia} |
| trends.keyword.spiking | trends | strategist | {keyword, search_volume, growth_pct, vertical} · (legacy · ver `trends.keyword.spike` Build 1.3) |
| trends.keyword.spike | trends_agent | strategist | {keyword, interest_over_time (0-100), delta_7d_pct} · emitido por TrendsAgent cuando delta 7d > 30% O interest >= 80 |
| marketplace.price.alert | alerts_agent | strategist, executive (CEO dashboard) | {sku_normalizado, titulo, precio_anterior, precio_actual, delta_pct, fuente: meli/fb, competitor_url} · emitido cuando drop ≥ 15% en últimas 24h |
| social.account.viral_detected | social | strategist | {account_id, platform: ig/tiktok, post_id, views, vertical} · (legacy · ver `social.account.trending` Build 2.3) |
| social.account.trending | social_agent | strategist, executive | {plataforma, username, seguidores, relevancia_score, fuente_query} · emitido por SocialAgent cuando una cuenta nueva (no existía antes) entra al catálogo `social_accounts` |
| social.reel.viral | social | strategist | {post_id, platform, views, engagement_rate, related_skus} |

### Dominio: Strategist y decisiones

| event_type | Productor | Consumidores | Payload clave |
|------------|-----------|--------------|---------------|
| recommendation.created | strategist_agent | executive, compliance_officer, sismo_sync | {recommendation_id, type, priority: Alta/Media/Baja, action_description ≤300, expected_impact} · emitido por `persist_recommendations_from_briefing` en cada upsert nuevo desde un briefing · Build 3.3+ |
| recommendation.compliance.validated | compliance_officer | executive | {recommendation_id, status: aprobado/rechazado_compliance, motivo} |
| recommendation.approved | executive_agent | media_buyer, audit_log | {recommendation_id, approved_by ≤200} · emitido por `POST /api/v1/recommendations/{id}/approve` cuando la rec estaba en `pendiente` · Build 3.3+ |
| recommendation.rejected | executive_agent | audit_log | {recommendation_id, rejected_by ≤200, reason ≤300} · emitido por `POST /{id}/reject` · Build 3.3+ |
| recommendation.executed | media_buyer | strategist, audit_log | {recommendation_id, execution_id, external_ref} |
| recommendation.evaluated | strategist_agent | dashboard, audit_log | {recommendation_id, hit_rate_contribution: 0.0/0.5/1.0} · emitido por `evaluate_pending_recommendations` (cron 07:00 UTC) tras medir impacto en ventana 7d · Build 3.3+ |
| recommendation.measured | sismo_sync | strategist | {recommendation_id, actual_impact, hit_rate_contribution, learning} (deprecated · reemplazado por `recommendation.evaluated`) |

### Dominio: Media Buyer (pauta digital)

| event_type | Productor | Consumidores | Payload clave |
|------------|-----------|--------------|---------------|
| campaign.requested | strategist | compliance_officer | {campaign_id, platform: meta/google, budget, audience, sku_affected} |
| campaign.compliance.passed | compliance_officer | media_buyer | {campaign_id} |
| campaign.created | media_buyer | sismo_sync, audit_log | {campaign_id, platform, external_id, http_status: 200} |
| campaign.metrics.updated | media_buyer | strategist | {campaign_id, impresions, clicks, spend, conversions} |
| campaign.cap.reached | compliance_officer | media_buyer, executive | {campaign_id, cap_type, current, limit} |

### Dominio: Briefing diario y reportes

| event_type | Productor | Consumidores | Payload clave |
|------------|-----------|--------------|---------------|
| briefing.generation.started | scheduler | strategist, executive | {date, workspace_id} (futuro · cuando haya tracing por phase del pipeline) |
| briefing.published | executive_agent | audit_log, dashboard | {fecha: YYYY-MM-DD, num_acciones: int, modelo_usado: str} · emitido por ExecutiveAgent en cada upsert (incluye re-runs) · Build 3.1+ |
| briefing.action.approved | executive (web UI) | strategist | {briefing_id, action_id, approved_by} |
| briefing.action.rejected | executive (web UI) | strategist | {briefing_id, action_id, rejected_by, reason} |

### Dominio: Cross-system (ARGOS ⇄ SISMO V2)

| event_type | Productor | Consumidores | Payload clave |
|------------|-----------|--------------|---------------|
| sismo.inventory.synced | sismo_agent | strategist, dashboard | {total_skus, slow_count} · emitido por `sync_sismo_inventory_job` (cron 6h) tras persistir el snapshot del día en `sismo_inventory` · NO se emite si SISMO_API_URL vacío (skip silencioso) · Build 4.1+ |
| sismo.sales.daily.synced | sismo_sync | strategist, dashboard | {date, sales_count, total_amount} |
| sismo.customer.created | sismo_sync | whatsapp_agent | {customer_id, source: argos/web} |
| sismo.loanbook.snapshot | sismo_sync | score_engine | {snapshot_id, records_count, timestamp} |
| argos.recommendation.published | strategist | sismo_radar_sync | {recommendation_id, type, sku, action} |

## Versionado de eventos

- Cada evento tiene campo `version` semver
- Cambios non-breaking (agregar campo opcional al payload): bump minor
- Cambios breaking (renombrar campo, cambiar tipo, eliminar campo): bump major + migración documentada en docs/claude/phase_X.md
- Consumidores deben ser tolerantes a campos desconocidos (forward compatibility)

## Reglas de uso

1. Antes de emitir cualquier evento nuevo: registrarlo aquí primero
2. Antes de consumir un evento: verificar que esté listado y entender su payload
3. Los eventos se persisten en colección `argos_events` con TTL infinito (jamás se borran · ROG-A6)
4. Para queries analíticas se replica a una colección secundaria `argos_events_indexed` con índices por event_type, workspace_id, timestamp
5. Cada agente debe poder reconstruir su estado leyendo el bus desde un punto en el tiempo (event sourcing)
