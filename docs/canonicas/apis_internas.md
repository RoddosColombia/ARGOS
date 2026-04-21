# docs/canonicas/apis_internas.md

Endpoints REST entre módulos de ARGOS. No incluye integraciones externas (ver apis_externas.md) ni eventos asíncronos (ver eventos.md).

## Convenciones

- Prefijo: `/api/v1/`
- Auth: JWT con scope por rol (cliente, ceo, analista, sistema)
- Multi-tenant: header `X-Workspace-Id` obligatorio en todo request (ROG-A3)
- Response format: JSON con envelope `{success, data, error}`
- Errores: HTTP status code estándar + body con `{error_code, message, details}`

## Dominio: Score Engine (interno de ARGOS)

| Method | Endpoint | Producer del request | Función |
|--------|----------|---------------------|---------|
| POST | /api/v1/scoring/solicitar | whatsapp_agent | Crear solicitud KYC desde conversación WhatsApp |
| GET | /api/v1/scoring/{solicitud_id} | whatsapp_agent, executive web | Estado de una solicitud |
| POST | /api/v1/scoring/{solicitud_id}/documentos | whatsapp_agent | Adjuntar documentos enviados por cliente |
| POST | /api/v1/scoring/{solicitud_id}/evaluar | scheduler interno | Trigger evaluación (después de KYC completo) |
| PUT | /api/v1/scoring/{solicitud_id}/decision | analista web | Override manual de decisión (revisión manual) |
| GET | /api/v1/scoring/dashboard | executive web | KPIs del Score Engine para CEO |
| GET | /api/v1/scoring/export | analista web | Descarga CSV/Excel de scoring_solicitudes |
| GET | /api/v1/scoring/model/info | sistema | Versión actual del XGBoost en producción |

## Dominio: WhatsApp

| Method | Endpoint | Producer | Función |
|--------|----------|----------|---------|
| POST | /api/v1/whatsapp/webhook | mercately | Recibe mensajes entrantes (webhook firmado) |
| POST | /api/v1/whatsapp/send | strategist, executive, cobranza | Enviar mensaje saliente vía Mercately |
| GET | /api/v1/whatsapp/conversation/{phone} | executive web | Historial de conversación con un cliente |
| POST | /api/v1/whatsapp/handoff | whatsapp_agent | Disparar handoff a operador humano |
| GET | /api/v1/whatsapp/templates | sistema | Lista de templates aprobados por Meta |

## Dominio: Briefing y Strategist

| Method | Endpoint | Producer | Función |
|--------|----------|----------|---------|
| GET | /api/v1/briefing/{date} | executive web | Vista del Morning Briefing del día |
| GET | /api/v1/briefing/{date}/actions | executive web | Las 3 acciones priorizadas del día |
| POST | /api/v1/briefing/actions/{id}/approve | executive web | Aprobar una acción del briefing |
| POST | /api/v1/briefing/actions/{id}/reject | executive web | Rechazar acción + motivo |
| GET | /api/v1/recommendations | executive web | Listado de recomendaciones (filtros: estado, tipo, fecha) |
| GET | /api/v1/recommendations/{id} | executive web | Detalle + impact tracking |

## Dominio: Marketplace e inteligencia

| Method | Endpoint | Producer | Función |
|--------|----------|----------|---------|
| GET | /api/v1/marketplace/products | executive web | Top productos detectados (filtros: source, vertical, fecha) |
| GET | /api/v1/marketplace/competitors | executive web | Lista de competidores tracked |
| GET | /api/v1/marketplace/price-history/{sku} | executive web | Serie temporal de precios de un SKU |
| GET | /api/v1/social/accounts | executive web | Cuentas IG/TikTok tracked |
| GET | /api/v1/social/viral | executive web | Posts/reels virales del mes |
| GET | /api/v1/competitors/ads | executive web | Ads competitivos activos |

## Dominio: Media Buyer

| Method | Endpoint | Producer | Función |
|--------|----------|----------|---------|
| POST | /api/v1/campaigns | executive (post-approval) | Crear campaña Meta o Google |
| GET | /api/v1/campaigns | executive web | Listado campañas activas |
| GET | /api/v1/campaigns/{id} | executive web | Detalle + métricas en vivo |
| POST | /api/v1/campaigns/{id}/pause | executive web | Pausar campaña |
| GET | /api/v1/campaigns/{id}/audit | analista | Audit log completo de la campaña |

## Dominio: Cobranza

| Method | Endpoint | Producer | Función |
|--------|----------|----------|---------|
| POST | /api/v1/cobranza/cobro | sismo_radar (vía sync) | Recibir cobro programado desde RADAR |
| POST | /api/v1/cobranza/wava-webhook | wava | Webhook de confirmación de pago |
| GET | /api/v1/cobranza/customer/{customer_id} | executive web | Estado de cuenta del cliente |
| POST | /api/v1/cobranza/escalar | cobranza_orchestrator | Escalar caso de morosidad a humano |

## Dominio: Sync con SISMO V2

| Method | Endpoint | Producer | Función |
|--------|----------|----------|---------|
| GET (interno) | /api/v1/sismo/inventory | scheduler nightly + on-demand | Sincroniza inventario desde SISMO |
| GET (interno) | /api/v1/sismo/sales/{date} | scheduler nightly | Sincroniza ventas del día desde SISMO |
| GET (interno) | /api/v1/sismo/loanbook/snapshot | scheduler weekly | Snapshot de cartera para entrenamiento Score Engine |
| POST (interno) | /api/v1/sismo/customer | whatsapp_agent | Crea/actualiza cliente en SISMO desde ARGOS |
| POST (interno) | /api/v1/sismo/recommendation | strategist | Publica recomendación en SISMO |
| POST (interno) | /api/v1/sismo/score-result | score_engine | Persiste resultado de score en loanbook de SISMO |

## Dominio: Auth y workspace

| Method | Endpoint | Producer | Función |
|--------|----------|----------|---------|
| POST | /api/v1/auth/login | usuario interno | Login con credenciales · retorna JWT |
| GET | /api/v1/auth/me | usuario interno | Datos del usuario autenticado |
| GET | /api/v1/workspaces | usuario | Workspaces a los que pertenece el usuario |
| GET | /api/v1/health | monitoreo | Health check público |
| GET | /api/v1/health/deep | monitoreo | Health check con verificación de partners |

## Dominio: Audit log

| Method | Endpoint | Producer | Función |
|--------|----------|----------|---------|
| GET | /api/v1/audit | analista | Audit log filtrable (acción, usuario, fecha) |
| GET | /api/v1/audit/{event_id} | analista | Detalle de evento auditado |
