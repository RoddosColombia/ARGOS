# docs/canonicas/apis_internas.md

Endpoints REST entre módulos de ARGOS. No incluye integraciones externas (ver apis_externas.md) ni eventos asíncronos (ver eventos.md).

> **Auditado en Phase 2.5 · Build 2.5.1 (2026-04-29)**: cada endpoint marcado con su estado real vs código.
> Leyenda: ✅ Implementado · 🟡 Spec pendiente · ⚠️ Cambiado por pivote · ⛔ Obsoleto / movido fuera de ARGOS

## Convenciones

- Prefijo: `/api/v1/`
- Auth: JWT con scope por rol (`ceo`, `cgo`, `analista`, `sistema`, `cliente`)
- Multi-tenant: header `X-Workspace-Id` obligatorio en todo request (ROG-A3)
- Response format: JSON con envelope `{success, data, error}`
- Errores: HTTP status code estándar + body con `{error_code, message, details}`

## Dominio: Score Engine (pass-through al motor externo · ROG-S1 reescrita)

> ⚠️ **Cambio arquitectónico 2026-04-27**: el Score Engine vive en `https://github.com/RoddosColombia/roddos-scoring`. ARGOS hace pass-through HTTP. Los endpoints originales que asumían motor interno se reemplazaron.

| Estado | Method | Endpoint | Producer | Función |
|--------|--------|----------|----------|---------|
| ✅ v0.1 | POST | /api/v1/score/evaluate | whatsapp_agent (futuro), frontend test | Pass-through a `roddos-scoring`/v1/evaluate · ARGOS reenvía payload, devuelve response |
| ✅ v0.1 | GET | /api/v1/score/solicitudes | executive web | Lista de solicitudes leída read-only desde el cluster compartido |
| ✅ v0.1 | GET | /api/v1/score/config | frontend | Expone URL del Score Engine para banner del frontend |
| ⛔ obsoleto | POST | /api/v1/scoring/solicitar | — | Reemplazado por `/score/evaluate` pass-through |
| ⛔ obsoleto | POST | /api/v1/scoring/{solicitud_id}/documentos | — | KYC documental delegado al Score Engine externo |
| ⛔ obsoleto | POST | /api/v1/scoring/{solicitud_id}/evaluar | — | Trigger interno reemplazado por pass-through |
| ⛔ obsoleto | PUT | /api/v1/scoring/{solicitud_id}/decision | — | Override manual vive en admin web · ARGOS no muta |
| 🟡 Capa 4 | GET | /api/v1/scoring/dashboard | executive web | KPIs del Score Engine para CEO+CGO (datos leídos del shared DB) |
| 🟡 Capa 4 | GET | /api/v1/scoring/export | analista web | Descarga CSV/Excel desde shared DB |
| ⛔ obsoleto | GET | /api/v1/scoring/model/info | — | engine_version viaja en cada response del pass-through |

## Dominio: WhatsApp (Phase 3 · Capa 1)

> 🟡 Toda la familia es **spec · pendiente Phase 3 / Capa 1**. Ningún endpoint existe en código todavía.

| Estado | Method | Endpoint | Producer | Función |
|--------|--------|----------|----------|---------|
| 🟡 Capa 1 | POST | /api/v1/whatsapp/webhook | mercately | Recibe mensajes entrantes (webhook firmado) |
| 🟡 Capa 1 | POST | /api/v1/whatsapp/send | strategist, executive | Enviar mensaje saliente vía Mercately · debe pasar por `opt_in.can_send_proactive()` |
| 🟡 Capa 1 | GET | /api/v1/whatsapp/conversation/{phone} | executive web | Historial de conversación con un cliente |
| 🟡 Capa 1 | POST | /api/v1/whatsapp/handoff | whatsapp_agent | Disparar handoff a operador humano |
| 🟡 Capa 1 | GET | /api/v1/whatsapp/templates | sistema | Lista de templates aprobados por Meta |
| 🟡 Capa 1 | GET | /api/v1/whatsapp/conversations | executive web | Lista paginada con filtros (outcome, intent, fecha) |

## Dominio: Briefing y Strategist (Capa 1 implementada · brief unificado en Phase 2.5)

| Estado | Method | Endpoint | Producer | Función |
|--------|--------|----------|----------|---------|
| ✅ v0.1 | GET | /api/v1/briefing/{date} | frontend (CEO + CGO) | Vista del Morning Briefing del día (mismo contenido para ambos roles · ROG-G1) |
| ✅ v0.1 | GET | /api/v1/briefing/{date}/actions | frontend | Las 3 acciones priorizadas del día |
| ✅ v0.1 | GET | /api/v1/recommendations | frontend | Listado de recomendaciones (filtros: estado, tipo, fecha) |
| ✅ v0.1 | GET | /api/v1/recommendations/{id} | frontend | Detalle + impact tracking |
| ✅ v0.1 | POST | /api/v1/recommendations/{id}/approve | frontend | Aprobar recomendación · validación role vs `approval_required_role` (Phase 2.5 Build 2.5.5) |
| ✅ v0.1 | POST | /api/v1/recommendations/{id}/reject | frontend | Rechazar + motivo |

## Dominio: Marketplace e inteligencia (Capa 1 implementada)

| Estado | Method | Endpoint | Producer | Función |
|--------|--------|----------|----------|---------|
| ✅ v0.1 | GET | /api/v1/marketplace/products | frontend | Top productos detectados (filtros: source, vertical, fecha) |
| 🟡 Capa 4 | GET | /api/v1/marketplace/competitors | frontend | Lista de top vendedores MELI tracked (Account intel) |
| 🟡 Capa 4 | GET | /api/v1/marketplace/price-history/{sku} | frontend | Serie temporal de precios de un SKU |
| ✅ v0.1 | GET | /api/v1/social/accounts | frontend | Cuentas IG/TikTok tracked |
| 🟡 Capa 4 | GET | /api/v1/social/viral | frontend | Posts/reels virales del mes |
| ✅ v0.1 | GET | /api/v1/competitors/ads | frontend | Ads competitivos activos (Meta + Google) |
| 🟡 Capa 4 | GET | /api/v1/account-intel/playbook/{competitor_id} | frontend | Playbook extraído por competidor (Account intel agent) |
| 🟡 Capa 4 | GET | /api/v1/portfolio/suggestions | frontend | Top SKUs sugeridos para sourcear (Portfolio agent · weekly) |

## Dominio: Pricing engine (Capa 5)

| Estado | Method | Endpoint | Producer | Función |
|--------|--------|----------|----------|---------|
| 🟡 Capa 5 | GET | /api/v1/pricing/suggestions | frontend | Sugerencia de precio diaria por SKU activo con justificación competitiva |
| 🟡 Capa 5 | POST | /api/v1/pricing/{sku}/apply | sistema (Plano 1) o CGO (Plano 2) | Aplicar ajuste de precio · valida envelope con Compliance Officer |
| 🟡 Capa 5 | GET | /api/v1/pricing/history/{sku} | frontend | Histórico de cambios de precio + impacto observado |

## Dominio: Media Buyer (Capa 5)

| Estado | Method | Endpoint | Producer | Función |
|--------|--------|----------|----------|---------|
| 🟡 Capa 5 | POST | /api/v1/campaigns | executive (post-approval Plano 2) | Crear campaña Meta o Google |
| 🟡 Capa 5 | GET | /api/v1/campaigns | frontend | Listado campañas activas |
| 🟡 Capa 5 | GET | /api/v1/campaigns/{id} | frontend | Detalle + métricas en vivo |
| 🟡 Capa 5 | POST | /api/v1/campaigns/{id}/pause | sistema (Plano 1 si CTR<X) o CGO | Pausar campaña |
| 🟡 Capa 5 | GET | /api/v1/campaigns/{id}/audit | analista | Audit log completo de la campaña |

## Dominio: Cobranza

> ⛔ **Movido fuera de ARGOS (Visión 2.1 sección 4.7)**: cobranza recurrente vive íntegra en SISMO V2 (RADAR + integración Mercately propia + Wava). ARGOS no dispara ni procesa.

| Estado | Method | Endpoint | Producer | Función |
|--------|--------|----------|----------|---------|
| ⛔ obsoleto | POST | /api/v1/cobranza/cobro | — | RADAR ya no notifica a ARGOS |
| ⛔ obsoleto | POST | /api/v1/cobranza/wava-webhook | — | Wava notifica a SISMO directamente |
| ⛔ obsoleto | GET | /api/v1/cobranza/customer/{customer_id} | — | Estado de cuenta consultable en SISMO |
| ⛔ obsoleto | POST | /api/v1/cobranza/escalar | — | Escalamiento de morosidad vive en SISMO |

## Dominio: SISMO V2 (sync read implementado · write spec en Capa 0/1)

### Lectura ARGOS ← SISMO (Capa 1 ya implementada)

| Estado | Method | Endpoint | Producer | Función |
|--------|--------|----------|----------|---------|
| ✅ v0.1 | (interno) | argos.partners.sismo · `GET /inventory/repuestos` | scheduler 6h + on-demand | Sincroniza inventario desde SISMO |
| ✅ v0.1 | (interno) | argos.partners.sismo · `GET /sales/daily` | scheduler 01:00 UTC | Sincroniza ventas del día |
| ✅ v0.1 | GET | /api/v1/sismo/inventory | frontend | Lista inventario sincronizado |
| ✅ v0.1 | GET | /api/v1/sismo/sales | frontend | Lista ventas sincronizadas |
| 🟡 Capa 1 | (interno) | argos.partners.sismo · `GET /loanbook/comportamiento-pago/{customer_id}` | whatsapp_agent | Score comportamental para bypass F3 (ROG-S2) |

### Escritura ARGOS → SISMO (Capa 1 · spec ampliada en Build 2.5.1)

> 🟡 **4 endpoints nuevos**: spec en `integraciones_sismo.md` ampliada · trabajo paralelo del equipo SISMO en Capa 0.

| Estado | Method | Endpoint (lado SISMO) | Producer ARGOS | Función |
|--------|--------|----------------------|----------------|---------|
| 🟡 Capa 1 | POST | SISMO `/api/sismo/invoices` | whatsapp_agent post-Wava confirm | Solicita factura con validaciones (idempotency por payment_ref) |
| 🟡 Capa 1 | POST | SISMO `/api/sismo/customers/activate` | whatsapp_agent post-F4 cash | Activa cliente nuevo (RiskSeal antifraude OK) |
| 🟡 Capa 1 | POST | SISMO `/api/sismo/loans/initiate` | whatsapp_agent post-F2 score+Wava | Inicia loan RDX Leasing |
| 🟡 Capa 1 | POST | SISMO `/api/sismo/payments/confirm` | whatsapp_agent post-Wava webhook | Confirma pago para que SISMO actualice saldo |

## Dominio: Auth y workspace (implementado · CGO nativo en Phase 2.5)

| Estado | Method | Endpoint | Producer | Función |
|--------|--------|----------|----------|---------|
| ✅ v0.1 | POST | /api/v1/auth/login | frontend | Login con credenciales · retorna JWT |
| ✅ v0.1 | GET | /api/v1/auth/me | frontend | Datos del usuario autenticado |
| 🟡 Phase 2.5 | (cambio schema) | users.role | seed | Agregar `cgo` como role nativo (Build 2.5.5) |
| ✅ v0.1 | GET | /api/v1/health | monitoreo | Health check público |
| ✅ v0.1 | GET | /api/v1/health/deep | monitoreo | Health check con verificación de partners |

## Dominio: Contacts y opt-in (Phase 2.5 · Build 2.5.3)

> 🟡 Spec · construir antes de Phase 3 para cumplir ROG-W1 preventivo.

| Estado | Method | Endpoint | Producer | Función |
|--------|--------|----------|----------|---------|
| 🟡 Phase 2.5 | POST | /api/v1/contacts/{phone}/opt-in | frontend, sistema, sales op | Registra opt-in con canal + consent_text_version |
| 🟡 Phase 2.5 | POST | /api/v1/contacts/{phone}/opt-out | frontend, sistema | Registra unsubscribe |
| 🟡 Phase 2.5 | GET | /api/v1/contacts/{phone}/opt-status | sistema | Lectura de estado opt-in vigente |
| 🟡 Phase 2.5 | GET | /api/v1/contacts | frontend | Listado de contactos con filtros |

## Dominio: Compliance Officer (Phase 2.5 · Build 2.5.4 versión Plano 1)

| Estado | Method | Endpoint | Producer | Función |
|--------|--------|----------|----------|---------|
| 🟡 Phase 2.5 | GET | /api/v1/compliance/envelope | frontend | Lectura del envelope vigente (CEO + CGO ven lo mismo) |
| 🟡 Phase 2.5 | POST | /api/v1/compliance/envelope | CEO (Plano 3) | Crear/actualizar envelope · audit_log |
| 🟡 Phase 2.5 | POST | /api/v1/compliance/validate | sistema (cualquier agente con acción Plano 1) | Devuelve {allowed, plano_required, reason} |

## Dominio: Audit log (Phase 2.5 · Build 2.5.2 hace que escriba)

| Estado | Method | Endpoint | Producer | Función |
|--------|--------|----------|----------|---------|
| 🟡 Phase 2.5 | (writer interno) | argos.services.audit.audit_write() | login, evaluate, recommendations, config | Persistencia del audit_log (cierra ROG-A12) |
| 🟡 Phase 2.5 | GET | /api/v1/audit | analista, CEO, CGO | Audit log filtrable (acción, role, fecha) |
| 🟡 Phase 2.5 | GET | /api/v1/audit/{event_id} | analista, CEO, CGO | Detalle de evento auditado |

## Dominio: Configuración interna (implementado)

| Estado | Method | Endpoint | Producer | Función |
|--------|--------|----------|----------|---------|
| ✅ v0.1 | GET | /api/v1/config/categories | frontend | Catálogo de categorías activas |
| ✅ v0.1 | PATCH | /api/v1/config/categories/{slug} | frontend | Activar/desactivar categoría |
| ✅ v0.1 | POST | /api/v1/config/categories/request | frontend | Pedir nueva categoría (notification) |
| ✅ v0.1 | GET | /api/v1/config/queries | frontend | Lista de watch_queries |
| ✅ v0.1 | POST | /api/v1/config/queries | frontend | Crear/modificar watch_query |

## Resumen del estado del repo (por dominio)

| Dominio | Total endpoints | ✅ Implementado | 🟡 Spec | ⚠️ Cambiado | ⛔ Obsoleto |
|---------|----------------|-----------------|---------|--------------|--------------|
| Score Engine pass-through | 10 | 3 | 2 | 0 | 5 |
| WhatsApp | 6 | 0 | 6 | 0 | 0 |
| Briefing y Strategist | 6 | 6 | 0 | 0 | 0 |
| Marketplace e inteligencia | 8 | 4 | 4 | 0 | 0 |
| Pricing engine | 3 | 0 | 3 | 0 | 0 |
| Media Buyer | 5 | 0 | 5 | 0 | 0 |
| Cobranza | 4 | 0 | 0 | 0 | 4 |
| SISMO sync | 9 | 4 | 5 | 0 | 0 |
| Auth y workspace | 5 | 4 | 1 | 0 | 0 |
| Contacts y opt-in | 4 | 0 | 4 | 0 | 0 |
| Compliance Officer | 3 | 0 | 3 | 0 | 0 |
| Audit log | 3 | 0 | 3 | 0 | 0 |
| Config | 5 | 5 | 0 | 0 | 0 |
| **Total** | **71** | **26** | **36** | **0** | **9** |

**Lectura**: 26/71 (37%) endpoints están en código hoy. La mayoría del 50% restante son Phase 2.5 (alineación) + Capa 1-5 (revenue + intelligence). Los 9 obsoletos son los del dominio Cobranza (movido a SISMO) + 5 del Score Engine reemplazados por pass-through.
