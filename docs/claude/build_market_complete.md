# Build market-intelligence-complete · cierre del loop de inteligencia

## Objetivo declarado

Cerrar el ciclo de inteligencia de mercado antes de pasar a Score Engine:

1. **Delivery push del Morning Briefing por WhatsApp** a las 06:00 AM Bogotá.
2. **Alertas de precio en tiempo real** vía WhatsApp cuando un drop fuerte (≥15%) entra al bus.
3. **Historial navegable** del briefing en el dashboard (últimos 7 días).

Prerequisito: Phase 3 + Phase 4 completas. ARGOS ya genera, persiste y razona briefings · sólo faltaba entregarlos al canal donde el CEO efectivamente los va a leer.

## Qué se construyó

### 1. Twilio WhatsApp delivery del Morning Briefing

- **Cliente** · `argos/partners/twilio/client.py` · `TwilioWhatsAppClient` async (httpx) con HTTP Basic auth, context manager con MockTransport-friendly init (`_owns_client` flag igual que Sismo Build 4.1). Skip silencioso sin `TWILIO_ACCOUNT_SID/_AUTH_TOKEN/_WHATSAPP_FROM`.
- **NotificationsAgent** · `argos/agents/notifications/service.py` con:
  - `format_briefing_text(briefing)` · texto plano ≤1600 chars (límite Twilio): emoji ☕ + fecha + mercado_24h en una línea + top 3 acciones con prioridad + estado_mercado capeado.
  - `send_briefing_whatsapp(briefing, agent)` · skip silencioso si `agent.enabled=False` · captura `TwilioError` y degrada a `{sent: False, reason: ...}` en lugar de propagar la excepción al caller.
- **Hook en Executive** · `run_morning_briefing` ahora llama `send_briefing_whatsapp(briefing)` después de `publish_briefing` y propaga `whatsapp_sent` en el dict de retorno.
- **Cron movido** · `morning_briefing` ahora corre **11:00 UTC = 06:00 AM Bogotá** (antes 06:45 UTC = 01:45 AM local). El CEO recibe WhatsApp cuando se está despertando.

### 2. Alertas de precio en tiempo real

- **`notify_recent_price_alerts(db, workspace_id, threshold_pct=-15.0, lookback_minutes=60)`** · job recurrente que:
  1. Lee eventos `marketplace.price.alert` con `payload.delta_pct ≤ -15` en la última hora **sin marca** `metadata.whatsapp_notified`
  2. Por cada uno: formatea con `format_price_alert(payload)` (emoji ⚠️ + ARGOS · alerta precio + título + delta + nuevo/anterior con formato COP) y envía WhatsApp
  3. Marca `metadata.whatsapp_notified=True` + timestamp para dedupe en re-runs
- **Cron** · `IntervalTrigger(minutes=30)` · check cada 30 min · suficiente latencia para "tiempo real" cuando los Scout/Alerts ticks corren cada hora y emiten los eventos al bus.

### 3. Historial navegable del briefing

- **Endpoint nuevo** · `GET /api/v1/briefing/by-date/{YYYY-MM-DD}` con validación regex en path (FastAPI 400 si no matches `^\d{4}-\d{2}-\d{2}$`). Devuelve 404 si no hay briefing para esa fecha.
- **Frontend `/briefing`** · agregado `<div role="tablist" data-testid="briefing-date-selector">` con 7 botones (hoy + 6 días anteriores). El primero muestra "Hoy", los demás muestran `MM-DD`. Click sobre un día cambia el queryKey de TanStack Query: cuando `isToday=true` usa `/today` (con auto-refresh de 15 min), cuando es histórico usa `/by-date/{fecha}` (sin auto-refresh, dato inmutable). El header sigue mostrando la fecha formateada en español.

### 4. Tests

- **Backend** (`tests/backend/test_notifications.py`): 5 tests
  - `test_format_briefing_text_incluye_acciones_y_emoji` (puro)
  - `test_send_briefing_whatsapp_llama_twilio_y_devuelve_sid` (mock httpx)
  - `test_send_briefing_whatsapp_skip_silencioso_sin_credenciales`
  - `test_notify_recent_price_alerts_dedupe_y_threshold` (Mongo integration · valida que solo el evento ≥ 15% se notifica + dedupe de 2do run)
  - `test_format_price_alert_estructura_emoji` (puro)
- **Frontend** (`src/pages/BriefingPage.test.tsx`): 1 test nuevo
  - `date selector cambia el endpoint a /by-date/{fecha}` valida que click en otro día dispara fetch al endpoint correcto.

## Decisiones técnicas

- **Twilio API directo, no SDK** · `twilio` SDK trae dependencias pesadas y boilerplate de auth. La API es un POST simple `application/x-www-form-urlencoded` con HTTP Basic. Mantengo el patrón del repo (httpx + skip silencioso + MockTransport para tests).
- **Dedupe vía `metadata.whatsapp_notified`, no nueva colección** · El bus es append-only (ROG-A6) sobre `payload`. La regla NO prohíbe mutar `metadata`: ese campo está reservado para metadata de procesamiento (tracking, flags). El alternativo era una colección `notifications_sent` separada, pero agrega complejidad (otro índice, otro lookup join) sin ganancia.
- **Threshold del job en `-15%` hardcoded** · El `check_price_drops` job de Build 1.3 ya emite `marketplace.price.alert` cuando hay drop ≥ 15% (su threshold default es 15.0). El nuevo job re-aplica el threshold como safety check para no spamear si en el futuro el upstream baja su umbral. Si se quiere parametrizar a nivel workspace, agregar campo en `workspaces.settings.whatsapp_price_threshold_pct`.
- **Cron 11:00 UTC** · 06:00 AM Bogotá (UTC-5). Si el CEO viaja, el cron sigue siendo UTC y el WhatsApp llegará a las 06:00 hora Colombia. Si necesita ajuste por DST/timezone changes, parametrizar cuando llegue.
- **`format_briefing_text` capea cada acción a 120 chars y estado_mercado a 300** · Twilio corta a 1600 chars sin warning. Mejor capear nosotros con sentido editorial que esperar truncamiento a la mitad de un SKU.

## Cambios en canónicas

- `docs/canonicas/eventos.md` · sección nueva "Notificaciones" documenta que NotificationsAgent es un CONSUMER (no productor) del bus · muta `metadata.whatsapp_notified` para dedupe sin violar ROG-A6.

## Errores cometidos y cómo se resolvieron

| Error | Causa raíz | Solución | Prevención futura |
| --- | --- | --- | --- |
| Ruff I001 import block unsorted en `partners/twilio/__init__.py` | orden alfabético: `TwilioWhatsAppClient, TwilioError` debía ser `TwilioError, TwilioWhatsAppClient` | `ruff check --fix` resolvió automáticamente | Correr `ruff --fix` antes de cada commit · ya está integrado en pre-commit del CI |

## Deuda técnica generada

- **DT-017 · Sin retry/backoff en Twilio errors** · Si Twilio devuelve 503 al briefing del día, perdemos esa entrega (queda solo en /briefing del web). El próximo briefing es al día siguiente. Mitigación parcial: el price_alert_job corre cada 30 min, así que un fallo transitorio se reintenta. Para el briefing matutino, agregar un `retry=3` con backoff exponencial.
- **DT-018 · WhatsApp no propaga "rejected/approved" eventos del briefing al bus** · El CEO podría aprobar/rechazar acciones desde WhatsApp con replies (Build 5+). Por ahora la entrega es one-way (push). Cuando llegue Mercately webhook (ROG-W1+ del WhatsApp Agent), reusar el mismo NotificationsAgent.
- **DT-019 · Threshold del price alert no es per-workspace** · Hardcoded a -15%. Si RODDOS escalas a más workspaces con verticales distintas, se va a querer por workspace. Aceptable hasta multi-tenant real.

## Métricas

- Tests: 5 backend nuevos en `test_notifications.py` + 1 frontend nuevo en `BriefingPage.test.tsx`
- Total: cuando full suite termine reporto número final
- Lint: `ruff check` clean tras 1 fix automático
- Build frontend: 174 modules · 475 KB JS · sin warnings

## Cierre

#### Build market-intelligence-complete · 2026-04-27
- Cerrado por: Andrés San Juan (CEO · approval pendiente) + Claude Code
- Rama: `build/market-intelligence-complete` → PR a `main`
- **Próximo: Score Engine** · Phase 2 score motor (clon del admin web) · ROG-S1 a S6 ya documentados
