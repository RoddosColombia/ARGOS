# Phase 3 · Capa 1 · WhatsApp Inbound Foundation

Bitácora de la primera capa de Phase 3: integración Mercately + routing de mensajes inbound.

---

## Build 3.1 · MercatelyClient + Inbound Poller + Intent Classifier (2026-05-14)

**Objetivo:** Construir la base de ingestión de mensajes WhatsApp vía Mercately y el routing inteligente ARGOS/SISMO.

**Contexto técnico Mercately:**
- Sin webhooks — polling obligatorio (GET per-phone, el endpoint global da HTTP 500)
- Auth: header `api-key` (lowercase, NO Bearer)
- Phone format: 12 dígitos `57XXXXXXXXXX` sin `+`
- URL base: `https://app.mercately.com/retailers/api/v1`

### Entregables

1. **`argos/partners/mercately/client.py`** — MercatelyClient async
   - `send_template`, `send_text`, `get_customer_by_phone`, `get_customer_messages`, `create_customer`
   - `normalize_phone()` con validación Colombia (10 → 12 dígitos con prefijo 57)
   - Skip silencioso sin `MERCATELY_API_KEY`
   - Context manager async (mismo pattern que TwilioWhatsAppClient)

2. **`argos/agents/whatsapp/intent_classifier.py`** — Haiku 4.5 classifier
   - 9 intents: 5 ARGOS (cotizar_repuesto, cotizar_moto, consulta_credito, consulta_general, onboarding) + 4 SISMO (pago_cuota, consulta_mora, soporte_credito, comprobante_pago)
   - Confidence threshold 0.7 — below routes to ARGOS (conservative)
   - Emite evento `whatsapp.message.classified` al bus
   - Fallback sin API key: `consulta_general` con confidence 0.0

3. **`argos/agents/whatsapp/sismo_forwarder.py`** — POST a SISMO webhook
   - Header `X-Mercately-Secret` para autenticación
   - Non-blocking en fallo de SISMO (log + continúa)
   - Emite evento `whatsapp.message.forwarded_sismo`

4. **`argos/agents/whatsapp/inbound_poller.py`** — Polling loop
   - Lee phones activos de `contacts` (opt-in · ROG-W1)
   - Per-phone GET conversations desde Mercately
   - Filtra inbound por timestamp > last_seen
   - Persiste last_seen en `mercately_polling_state`
   - Pasa a IntentClassifier → si SISMO, forward

5. **Config:** `MERCATELY_API_KEY`, `MERCATELY_POLL_INTERVAL_S` (default 30), `SISMO_INBOUND_WEBHOOK_URL`, `MERCATELY_WEBHOOK_SECRET`

6. **Scheduler:** job `mercately_inbound_poll` registrado con IntervalTrigger cada `MERCATELY_POLL_INTERVAL_S`. Se desactiva con `MERCATELY_POLL_INTERVAL_S=0`.

7. **Collection:** `mercately_polling_state` con índice (phone, workspace_id) unique

### Tests (48 nuevos)

- `test_mercately_client.py` — 18 tests: normalize_phone, skip silencioso, context manager, 5 métodos con MockTransport, error handling, header api-key
- `test_intent_classifier.py` — 16 tests: intent sets, routing logic, confidence threshold, Anthropic mock, fallback, ClassificationResult frozen
- `test_sismo_forwarder.py` — 5 tests: skip sin URL, forward success/failure, header, truncation
- `test_inbound_poller.py` — 9 tests: extract messages, filter outbound, filter by last_seen, sort, polling flow con mocks, SISMO forwarding

### ROGs cumplidas
- ROG-W1: solo pollea phones con opt-in de `contacts`
- ROG-W6: intent classifier asigna goal medible a cada mensaje
- ROG-A3: workspace_id en todas las queries
- ROG-A11: comunicación con SISMO vía API autenticada (X-Mercately-Secret)
- ROG-A7: stateless agents, stateful bus (eventos emitidos al bus)

### Estado: ✅ CERRADO

Tests: 154 passed (48 nuevos), 0 failed. Lint clean. Suite total del repo: 154+ tests.

---

## Build 3.2 · WhatsApp Agent conversacional — cotización de repuestos (2026-05-15)

**Objetivo:** Cerrar el gap donde ARGOS clasifica mensajes inbound pero no responde. Implementar el conversation handler que despacha respuestas por intent y el catalog search que busca productos en products_catalog enriquecidos con stock SISMO.

**Refs:** ROG-W6, ROG-W7

### Entregables

1. **`argos/agents/whatsapp/catalog_search.py`** — Búsqueda de catálogo para cotización
   - `_build_search_regex(query_text)` — keywords ≥ 3 chars, regex OR por palabra
   - `_get_latest_sync_date(db, workspace_id)` — fecha más reciente de sismo_inventory
   - `_get_sismo_stock(db, workspace_id, product_names, fecha)` — match fuzzy por nombre contra sismo_inventory
   - `search_catalog(db, query_text, workspace_id)` — búsqueda principal, retorna lista con nombre, precio, stock, stock_source (sismo|catalog), source, categoria, compatible_motos, permalink
   - MAX_RESULTS=5, MIN_QUERY_LENGTH=3 (filtra stopwords españolas de 2 letras: de, en, el)

2. **`argos/agents/whatsapp/conversation_handler.py`** — Dispatch por intent
   - `_format_product_response(products, query)` — formato WhatsApp con precio formateado, stock, motos compatibles
   - `_format_moto_placeholder()` / `_format_credit_placeholder()` / `_format_onboarding()` — templates estáticas
   - `_generate_general_response(message_text, anthropic_api_key)` — respuesta via Haiku 4.5 con system prompt RODDOS; fallback estático sin API key
   - `_register_contact(db, phone, workspace_id)` — upsert contacto con opt_in_whatsapp=True y opt_in_marketing nested
   - `_emit_response_event(db, ...)` — emite `whatsapp.message.responded` al bus argos_events
   - `handle_message(db, *, classification, message_text, phone, mercately_client, ...)` — dispatch principal, retorna `{responded, intent, outcome, response_preview}`
   - Outcomes ROG-W7: cotizado, sin_resultado, respondido_general, placeholder_moto, placeholder_credito, onboarding_nuevo, onboarding_existente, fallback, send_failed

3. **Integración `inbound_poller.py`** — Bloque `elif route_to == "argos" and whatsapp_reply_enabled` que llama `handle_message()` y contabiliza en `responded_argos`

4. **Safety switch:** `ARGOS_WHATSAPP_REPLY_ENABLED` (bool, default False) en config.py — clasifica pero no responde hasta habilitación explícita

5. **Scheduler:** `_mercately_inbound_poll_job()` pasa `whatsapp_reply_enabled=settings.whatsapp_reply_enabled` a `poll_inbound()`

### Tests (20 nuevos)

- `test_catalog_search.py` — 8 tests: regex building (single/multi/short/empty), search vacío, sin matches, con SISMO enrichment, fallback a catalog stock
- `test_conversation_handler.py` — 12 tests: format con/sin productos, out of stock, handle cotizar con/sin resultados, consulta general sin API key, onboarding crea contacto, placeholders moto/crédito, mercately disabled, poller reply enabled/disabled

### ROGs cumplidas
- ROG-W6: cada conversación tiene goal medible (outcome obligatorio)
- ROG-W7: outcomes tipados en cada respuesta
- ROG-W3: stock verificado contra SISMO antes de cotizar
- ROG-A3: workspace_id en todas las queries
- ROG-A7: stateless handler, eventos al bus

### Estado: ✅ CERRADO

Tests: 174 passed (20 nuevos), 0 failed. Lint clean. Suite total del repo: 174 passed, 153 skipped.

---

## Build 3.3 · WavaClient + webhook receiver + orden de pago (2026-05-16)

**Objetivo:** Integrar Wava como pasarela de pago Nequi/Daviplata. Crear el flujo cotización → confirmar_compra → orden Wava → webhook de confirmación.

**Contexto técnico Wava:**
- Auth: header `merchant-key` con WAVA_MERCHANT_KEY
- URL dev: `https://api.dev.wava.co/v1` · URL prod: `https://api.wava.co/v1`
- Webhooks: Wava hace POST a URL configurada en su dashboard. NO envía HMAC — verificación obligatoria vía GET /v1/orders/{id}
- Idempotency: campo `order_key` en el body del POST
- Gateway principal: Nequi (id=1)

### Entregables

1. **`argos/partners/wava/client.py`** — WavaClient async
   - `create_order(amount, description, shopper, gateway_id, order_key)` → POST /v1/orders
   - `get_order(order_id)` → GET /v1/orders/{orderId}
   - `get_gateways()` → GET /v1/orders/paymentGateways
   - `submit_daviplata_otp(order_id, otp)` → POST /v1/orders/{id}/daviplata-otp
   - `WavaShopper` dataclass con campos requeridos por Wava
   - `WavaOrder` dataclass con `from_response()` parser
   - Skip silencioso sin `WAVA_MERCHANT_KEY`
   - Context manager async (mismo pattern que MercatelyClient)

2. **`argos/api/v1/wava_webhook.py`** — Endpoint receptor
   - POST /api/v1/wava/webhook responde 200 inmediatamente (<5 seg)
   - Procesa en background: verifica status vía GET, actualiza wava_orders, emite eventos
   - Idempotente por wava_order_id
   - Eventos: `wava.payment.confirmed`, `wava.payment.failed`, `wava.payment.cancelled`, `wava.payment.refunded`
   - Audit log en cada webhook recibido + procesado (ROG-A12)
   - Exento de WorkspaceIdMiddleware (webhook público)

3. **Intent `confirmar_compra`** agregado al IntentClassifier (6 ARGOS intents ahora)
   - Prompt del classifier actualizado con nueva intención
   - Handler en conversation_handler.py:
     a) Lee datos del contacto (nombre, cédula, phone, email)
     b) Valida datos completos (cédula obligatoria)
     c) Crea orden Wava con gateway Nequi
     d) Persiste en wava_orders con status pending
     e) Responde por WhatsApp con instrucciones de aprobación Nequi
   - Outcomes nuevos ROG-W7: orden_creada, datos_incompletos, contacto_no_encontrado, wava_no_disponible, wava_error

4. **Collection `wava_orders`** con esquema completo en colecciones_mongo.md
   - Índices: (workspace_id, order_key) unique, (workspace_id, status), (workspace_id, wava_order_id)

5. **Config:** `WAVA_MERCHANT_KEY`, `WAVA_API_URL` (default https://api.dev.wava.co/v1)

6. **Integración:**
   - Router registrado en main.py
   - Scheduler pasa WavaClient al poll_inbound job
   - inbound_poller pasa wava_client al handle_message

### Tests (32 nuevos)

- `test_wava_client.py` — 14 tests: shopper, order dataclass, enabled/skip, context manager, create_order, get_order, get_gateways, error handling, daviplata OTP, merchant-key header
- `test_wava_webhook.py` — 8 tests: webhook 200 inmediato, invalid JSON, confirmed/failed/order not found/no merchant key/no order id, audit log
- `test_wava_order_flow.py` — 10 tests: doc_type mapping, wava disabled/no contact/missing cédula/order created/wava error, persist correctness, intent in ARGOS_INTENTS

### ROGs cumplidas
- ROG-A1: pago requiere aprobación humana en Nequi (Wava no auto-cobra)
- ROG-A3: workspace_id en todas las queries
- ROG-A12: audit log en cada webhook recibido + procesado
- ROG-W7: outcomes tipados obligatorios en confirmar_compra

### Estado: ✅ CERRADO

Tests: 206 passed (32 nuevos), 0 failed. Lint clean. Suite total del repo: 206 passed, 153 skipped.
