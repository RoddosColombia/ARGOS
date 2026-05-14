# Phase 3 · Capa 1 · WhatsApp Inbound Foundation

## Estado actual

Build 3.1 cerrado (2026-05-14). Base de ingestión WhatsApp implementada:
- MercatelyClient async con skip silencioso y normalización phone Colombia
- IntentClassifier (Haiku 4.5) con 9 intents y routing ARGOS/SISMO
- SismoForwarder non-blocking con evento al bus
- InboundPoller registrado en scheduler (cada 30s default)
- 48 tests nuevos, 154 total passing

## Próximos builds sugeridos

### Build 3.2 · WhatsApp Agent conversacional (cotización repuestos)
- Flujo F1: cliente pide cotización → ARGOS consulta catálogo → responde precio/disponibilidad
- Integración con `products_catalog` para búsqueda de SKUs
- Session management en `agent_sessions` collection
- Outcome tagging (ROG-W7)
- Handoff a humano (ROG-W4)

### Build 3.3 · WhatsApp Agent flujo crédito (F3)
- Flujo F3: cliente consulta crédito → ARGOS hace pass-through a `roddos-scoring`
- Integración con Score Engine contract (ROG-S1)
- Notificación de decisión por WhatsApp vía Mercately (ROG-S6)

### Build 3.4 · SISMO poller deactivation
- Validar que ARGOS procesa 100% del tráfico inbound correctamente
- Desactivar poller de SISMO V2 (`MERCATELY_POLL_INTERVAL_S=0` en SISMO)
- ARGOS como single gateway WhatsApp

## Dependencias externas pendientes
- Credenciales Mercately de producción (MERCATELY_API_KEY)
- Endpoint SISMO inbound webhook (SISMO_INBOUND_WEBHOOK_URL)
- Activar opt-in de phones en collection `contacts` (al menos phone del CEO para smoke test)
