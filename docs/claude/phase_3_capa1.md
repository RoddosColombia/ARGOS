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
