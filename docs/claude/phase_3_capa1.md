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
