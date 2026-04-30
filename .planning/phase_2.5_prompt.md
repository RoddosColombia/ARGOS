# .planning/phase_2.5_prompt.md

# PROMPT DETALLADO PARA CLAUDE CODE — PHASE 2.5 ALINEACIÓN

Este es el prompt operativo de la **Capa 0 · Phase 2.5 · Alineación y plomería** que precede a Phase 3 (WhatsApp commerce). Se ejecuta tras la Visión 2.1 y antes de cualquier código de canal comercial.

Phase 2.5 es la corrección formal del repo tras los pivotes de Phase 2 (Score Engine pass-through) y la articulación de la tesis competitiva 18 meses contra MELI. Sin esta phase cerrada limpia, Phase 3 hereda contradicciones documentales (CLAUDE.md vs código), ROGs incumplidas (A12 audit_log, W1 opt-in), y plomería diferida (Builds 0.6-0.9, scheduler in-memory) que después escalan en costo cuando entre el canal comercial.

---

## Contexto previo OBLIGATORIO de leer antes de empezar

Lee en este orden y en su totalidad:

1. `/CLAUDE.md` (raíz del repo) — versión 2.1 con todas las ROGs incluyendo la nueva categoría ROG-G
2. `/docs/VISION_2_1.md` — documento ejecutivo maestro vigente (supersede VISION_2_0.md)
3. `/docs/canonicas/README.md` y luego todos los `.md` dentro de `/docs/canonicas/`
4. `/docs/knowledge/README.md` + `/docs/knowledge/stack.md` + `/docs/knowledge/partners.md`
5. `/docs/claude/README.md` + `/docs/claude/phase_0_bootstrap.md` + `/docs/claude/phase_1_marketplace.md` + `/docs/claude/phase_2_score_engine.md` + `/docs/claude/errores_recurrentes.md` + `/docs/claude/deuda_tecnica.md`

Si encuentras alguna ambigüedad entre esta especificación y los documentos anteriores, los documentos canónicos ganan. Detén el trabajo y pregunta al CEO.

---

## Objetivo de Phase 2.5

Dejar el muro de carga firme antes de meter código de Phase 3. **Sin código de negocio nuevo en esta phase · solo plomería, alineación documental, governance, y cleanup de deuda diferida.**

Tres ejes:

1. **Alineación documental**: que CLAUDE.md, canónicas, agentes, eventos del bus y APIs estén sincronizados con el código real y con la Visión 2.1.
2. **Plomería estructural**: que las ROGs incumplidas (A12 audit_log, W1 opt-in, A6 metadata mutation, S5 contract test) queden enforzadas en código, no solo en documento.
3. **Cleanup de deuda diferida**: cerrar Builds 0.6-0.9 pendientes (Langfuse, baseline operativo, formalización credenciales Meta/Google) y resolver DT-004 (scheduler in-memory).

**Criterio de cierre:** todos los items del checklist final marcados ✅. Tag `phase-2.5-closed` en el repo.

---

## Builds incluidos en Phase 2.5

### Build 2.5.1 — Alineación documental + canónicas sincronizadas

**Tareas:**
- Verificar que `CLAUDE.md` (versión 2.1) está commiteado y que `docs/VISION_2_1.md` existe en el repo (ya entregados por Claude.ai · solo verificar y commitear si falta)
- Auditar `docs/canonicas/apis_internas.md` y marcar cada endpoint como uno de: `implementado vX.Y`, `spec · pendiente phase_N`, `obsoleto`. No debe haber ambigüedad sobre qué existe en código y qué es spec.
- Auditar `docs/canonicas/colecciones_mongo.md` y marcar cada colección como `implementada` o `spec · pendiente phase_N`. Documentar que `contacts` se construye en Build 2.5.3 de esta phase.
- Auditar `docs/canonicas/eventos.md` y marcar cada evento como `publicado en código` o `spec · pendiente`.
- Auditar `docs/knowledge/agents/` — confirmar que todos los archivos existen para los 14 agentes. Crear los faltantes:
  - `sku_canonicalizer.md` (nuevo · spec del agente, se construirá en Capa 4)
  - `portfolio.md` (nuevo · spec del agente, se construirá en Capa 4)
  - `account_intel.md` (nuevo · spec del agente, se construirá en Capa 4)
  - `pricing_engine.md` (nuevo · spec del agente, se construirá en Capa 5)
- Crear `docs/canonicas/score_engine_contract.md` con schema JSON versionado del Score Engine. Definir versión inicial `v1` con campos canónicos `decision`, `score_final`, `solicitud_id`, `engine_version`, `narrativa`, `regla_dura_aplicada`, `partners_consultados`, `created_at`. Coordinar con Iván Echeverri para validar el schema vs realidad de `roddos-scoring`.
- Ampliar `docs/canonicas/integraciones_sismo.md` con la sección **dirección ARGOS → SISMO de escritura**: 4 endpoints (`POST /api/sismo/invoices`, `POST /api/sismo/customers/activate`, `POST /api/sismo/loans/initiate`, `POST /api/sismo/payments/confirm`) con schema JSON, idempotency keys, retry policy, comportamiento esperado en degradación SISMO. **Esta es spec, la implementación del lado SISMO la hace el equipo SISMO en paralelo. La implementación del lado ARGOS arranca en Capa 1.**

**Criterio de éxito:**
- Cualquier dev nuevo puede leer las canónicas y saber qué está implementado vs qué es spec sin ambigüedad
- `score_engine_contract.md` validado por Iván
- 4 endpoints SISMO write con schema JSON formal y dummy mocks listos para Capa 1

### Build 2.5.2 — Audit log writers (cierra ROG-A12 y DT-025)

**Tareas:**
- Crear módulo `argos/services/audit.py` con función helper `audit_write(workspace_id, actor, action, target, metadata)` que persiste en `audit_log` con timestamp y `_id` ULID
- Identificar todos los call sites donde una acción debería auditarse y agregar la llamada:
  - `auth/api.py` login exitoso y fallido
  - `api/v1/score.py` `/evaluate` (cumple ROG-S4)
  - `api/v1/recommendations.py` approve/reject
  - `api/v1/config.py` cambios de queries y categories
  - `api/v1/scout.py` overrides manuales
  - `agents/notifications/service.py` send WhatsApp/email (cuando llegue Phase 3)
- Schema de `audit_log` documentado en `docs/canonicas/colecciones_mongo.md`:
  - `_id` ULID
  - `workspace_id` indexed
  - `timestamp` indexed
  - `actor: {role, user_id, source}` (role: `ceo|cgo|sistema|cliente|analista`)
  - `action` (string dot.notation, ej: `auth.login.success`, `score.evaluate.requested`)
  - `target` (objeto opcional con id del recurso afectado)
  - `metadata` (objeto opcional con contexto)
- Tests unitarios: `test_audit_writer.py` con 5+ casos cubriendo login, evaluate, recommendations approve, config change
- Verificar en CI que `pytest --cov=argos.services.audit --cov-fail-under=90`

**Criterio de éxito:**
- Cierra DT-025 (`docs/claude/deuda_tecnica.md` actualizado)
- Cualquier acción crítica del sistema deja huella consultable en `audit_log`
- ROG-A12 enforzada en código, no solo en CLAUDE.md

### Build 2.5.3 — Collection contacts + opt-in registry (cierra ROG-W1 preventivo)

**Tareas:**
- Crear `argos/db/collections.py` constante `CONTACTS = "contacts"`
- Crear índices en `argos/db/indexes.py` para `contacts`:
  - `(workspace_id, phone_number)` unique
  - `(workspace_id, opt_in_marketing.status)` para queries de outbound
  - `(workspace_id, last_message_at)` descending para recent activity
- Schema documentado en `docs/canonicas/colecciones_mongo.md`:
  - `_id` ULID
  - `workspace_id` indexed
  - `phone_number` (E.164)
  - `name` (opcional)
  - `customer_id_sismo` (opcional · null si aún no es cliente RODDOS)
  - `opt_in_marketing: {status: opted_in|opted_out|pending, captured_at, channel: sms|web|whatsapp_inbound|sales_call, consent_text_version, captured_by}` 
  - `opt_in_utility` (idem)
  - `last_message_at`
  - `created_at`, `updated_at`
- Crear endpoint `POST /api/v1/contacts/{phone_number}/opt-in` con payload `{type: marketing|utility, channel, consent_text_version, captured_by}`
- Crear endpoint `POST /api/v1/contacts/{phone_number}/opt-out` que registra unsubscribe
- Crear endpoint `GET /api/v1/contacts/{phone_number}/opt-status` lectura
- Helper `argos/services/opt_in.py:can_send_proactive(phone_number, type)` que devuelve `(allowed: bool, reason: str)`. **Phase 3 debe llamar este helper antes de cualquier outbound.** Si retorna `False`, se bloquea el envío y se loggea.
- Tests: `test_opt_in_registry.py` con casos de opt-in, opt-out, contacto inexistente, opt-in expirado (si aplica policy de expiración).

**Criterio de éxito:**
- ROG-W1 enforzable en código antes de que entre Phase 3
- Endpoints REST funcionales con audit_log emitiéndose en cada cambio
- Test coverage ≥85% en módulo

### Build 2.5.4 — Compliance Officer Plano 1 (envelope spending caps + veto framework)

**Tareas:**
- Crear `argos/agents/compliance_officer/` con módulos:
  - `service.py` con clase `ComplianceOfficer` que provee métodos `validate_action(action, plano)`, `is_within_envelope(action_type, params)`, `get_envelope(action_type)`
  - `envelope.py` con definición canónica del envelope inicial leído de colección `compliance_envelope`
- Crear colección `compliance_envelope` con schema:
  - `_id` ULID
  - `workspace_id`
  - `action_type` (ej: `pricing.adjust_meli`, `bidding.adjust_meta`, `ad_set.pause`)
  - `envelope: {min: number, max: number, unit: string}`
  - `plano` (1, 2 o 3)
  - `approved_by` (CEO user_id)
  - `approved_at`
  - `active`
- Seed inicial del envelope con valores conservadores (revisar con CEO):
  - `pricing.adjust_meli`: ±5% sobre precio base
  - `bidding.adjust_meta`: ±10% sobre bid actual
  - `ad_set.pause`: permitido si CTR<X durante Y horas (X y Y configurables)
  - `creative.suggest`: permitido para sugerir, NO ejecutar (requiere Plano 2)
- Endpoint `GET /api/v1/compliance/envelope` para consultar
- Endpoint `POST /api/v1/compliance/envelope` (solo CEO) para crear/actualizar
- Endpoint `POST /api/v1/compliance/validate` que recibe `{action_type, params, requested_by}` y devuelve `{allowed: bool, plano_required: 1|2|3, reason: string}`
- Tests: `test_compliance_officer.py` con casos dentro/fuera de envelope, escalation a Plano 2/3, audit_log writes

**Criterio de éxito:**
- ROG-A2 y ROG-A10 enforzables en código
- Compliance Officer es agente vivo (no solo ficha de spec) listo para integrarse con futuro Media Buyer y Pricing engine
- Cualquier agente puede llamar `compliance.validate_action(...)` antes de ejecutar

### Build 2.5.5 — CGO role nativo + multi-recipient brief delivery (ROG-G1)

**Tareas:**
- Actualizar schema `users` en `argos/db/collections.py` y validators:
  - Campo `role` con enum `ceo | cgo | analista | sistema | cliente`
  - `cgo` ahora es rol nativo
- Seed `cgo` user para Iván Echeverri en `argos/db/seed.py` (ENV vars: `CGO_EMAIL`, `CGO_PASSWORD_HASH`, `CGO_USER_ID`)
- Actualizar `auth/deps.py` para reconocer rol `cgo` con permisos:
  - Read en todos los endpoints que lee CEO
  - Write en endpoints de approval Plano 2
  - Read-only en endpoints de approval Plano 3
- Endpoint `POST /api/v1/recommendations/{id}/approve` ahora valida que el role del JWT coincida con el `approval_required_role` del recommendation
- Schema de `recommendations` extendido con campo `approval_required_role: ceo | cgo | none`
- Helper `argos/services/brief_delivery.py:send_brief_to_leadership(brief)` que envía el mismo brief a CEO + CGO simultáneamente vía WhatsApp + email + dashboard. ROG-G1 enforzada.
- Frontend: actualizar `Sidebar.tsx` para mostrar items basados en `role` del JWT (CEO ve todo, CGO ve todo en read pero approval queue filtrada a Plano 2)
- Frontend: nueva página `/approvals` con cola filtrada por role
- Tests: `test_cgo_role.py` (auth), `test_brief_delivery.py` (envío simultáneo), `test_recommendation_approval.py` (validación de role)

**Criterio de éxito:**
- ROG-G1 enforzada: brief siempre se entrega a CEO + CGO simultáneamente
- ROG-G2 enforzada: approval Plano 2 solo lo aprueba CGO, Plano 3 solo CEO
- ROG-G3 enforzada: audit_log registra qué role aprobó cada acción

### Build 2.5.6 — Score Engine contract test en CI semanal (ROG-S5)

**Tareas:**
- Crear `tests/contract/test_score_engine_contract.py` que:
  - Lee schema canonical de `docs/canonicas/score_engine_contract.md` (parseando JSON code block)
  - Envía payload conocido al Score Engine real (URL desde env var `SCORE_ENGINE_API_URL`)
  - Valida que el response cumple el schema (campos requeridos presentes, tipos correctos, `engine_version` formato esperado)
  - Falla con mensaje específico si hay mismatch
- Workflow `.github/workflows/contract-tests.yml` que corre semanal (lunes 06:00 UTC) y on-demand
- Job notifica a Slack/email si falla (configurable via `CONTRACT_TEST_NOTIFY_URL` env var)
- Documentar el flujo en `docs/canonicas/score_engine_contract.md` sección "Validación continua"

**Criterio de éxito:**
- Si Iván cambia el schema sin avisar, el sistema notifica antes de que rompa producción
- ROG-S5 cumplida operativamente, no solo en regla

### Build 2.5.7 — APScheduler persistente (cierra DT-004)

**Tareas:**
- Migrar APScheduler de `MemoryJobStore` a `MongoDBJobStore` (tabla `apscheduler_jobs` en cluster ARGOS)
- Configurar coalescing y misfire_grace_time apropiados (default 60 seg para jobs daily, 300 seg para weekly)
- Documentar en `docs/canonicas/colecciones_mongo.md` la colección `apscheduler_jobs`
- Test integration que verifica que jobs sobreviven restart del proceso
- Update `docs/claude/deuda_tecnica.md` marcando DT-004 como resuelta

**Criterio de éxito:**
- Si Render reinicia el backend, los jobs scheduled no se pierden
- Test de restart pasa en CI

### Build 2.5.8 — Builds 0.6-0.9 cleanup (Langfuse + baseline + credenciales)

**Tareas:**
- **Build 0.7 · Langfuse self-hosted**: deploy Langfuse en Render con PostgreSQL gratis. SDK Langfuse integrado en backend para wrappear todas las llamadas a Anthropic SDK. Dashboard Langfuse accesible en `https://argos-langfuse.onrender.com` (subdomain interno). Documentar en `docs/canonicas/integraciones_externas.md` y `partners.md`.
- **Build 0.8 · Formalización credenciales**: System User ARGOS en BM RODDOS + Service Account ARGOS en MCC RODDOS · documentar en `docs/knowledge/partners.md` con instrucciones de rotación de credenciales (cumple ROG-A4 y A11). PoC RiskSeal agendada (acción CEO en paralelo).
- **Build 0.9 · Baseline operativo**: capturar las 6 métricas de Visión 2.0 sección 5 desde reportes SISMO (ingreso mensual repuestos, días promedio inventario top 100 SKU, margen bruto repuestos, ROAS pauta digital, horas/semana CEO en investigación de mercado, tasa de éxito de decisiones). Persistir en colección `system_health` con `_id="baseline_phase_2.5_closed"`. Vista `/baseline` (read-only) que muestra el snapshot.

**Criterio de éxito:**
- Todas las llamadas LLM observables en Langfuse con costo y latencia
- Credenciales Meta/Google rotables y documentadas
- Baseline visible en `argos.roddos.com/baseline`

### Build 2.5.9 — ROG-A6 metadata mutation policy formalizada

**Tareas:**
- Auditar uso actual de mutación de metadata sobre `argos_events` en `agents/notifications/service.py:153-159`
- Decidir entre dos paths:
  - **Path A**: legalizar formalmente la mutación con regla específica en CLAUDE.md (ya hecho parcialmente en ROG-A6 reescrita) y agregar test que verifica que solo se mutan campos permitidos (`metadata.whatsapp_notified`, `metadata.email_notified`, `metadata.escalated`).
  - **Path B**: mover el flag a colección colateral `notifications_dispatch_log` que es append-only sin necesidad de mutar el bus.
- Recomendación: Path A en Phase 2.5 (menor delta de código), revisar Path B en Phase 6+ si la lista de flags crece más allá de 3-5.
- Si Path A: agregar test `test_argos_events_metadata_mutation.py` que falla si se mutan campos fuera de la lista permitida.

**Criterio de éxito:**
- ROG-A6 enforzada en código consistente con su redacción
- Cualquier mutación futura no permitida hace fallar tests

---

## Trabajo paralelo a coordinar (NO bloquea Phase 2.5 pero debe iniciar)

- **Equipo SISMO V2**: kick-off para implementar los 4 endpoints de escritura ARGOS → SISMO definidos en `docs/canonicas/integraciones_sismo.md` (ampliada en Build 2.5.1). Dependencia para Capa 1.
- **Wava onboarding**: arrancar el proceso (2-3 semanas estimadas). Dependencia para Capa 2.
- **Mercately**: confirmación con BSP de si la WABA de SISMO Build 14 se reusa para ARGOS o si Argos requiere WABA dedicada.
- **RiskSeal**: agendar PoC. Lo invoca `roddos-scoring`, no ARGOS, pero la cuenta debe estar viva.
- **Iván Echeverri (CGO)**: provisionar credenciales (email, password) en `.env` de Render para que el seed de Build 2.5.5 cree su user con role `cgo`.

---

## Reglas de operación durante Phase 2.5

1. **Cada commit que toque una integración o canónica actualiza la canónica correspondiente en el mismo PR.**
2. **Cada error >30 min de debug se registra en `/docs/claude/errores_recurrentes.md` el mismo día.**
3. **Cada build cerrado actualiza `/docs/claude/phase_2.5_alineacion.md` con: decisiones tomadas, errores resueltos, deuda generada o cerrada.**
4. **Conventional Commits con scope obligatorio.** Ej: `feat(compliance): add envelope validator` con `Refs: phase_2.5/build_2.5.4`
5. **Tests obligatorios para todos los Builds críticos (audit, opt-in, compliance, brief_delivery, contract test).**
6. **Cobertura de coverage ahora enforzada en CI**: `pytest --cov-fail-under=80` en módulos críticos. Ajustar `.github/workflows/ci.yml` en Build 2.5.2.
7. **NO escribir código de Phase 3 (WhatsApp commerce) en Phase 2.5.** Solo plomería. Si se siente la tentación → registrar en deuda_tecnica como anticipado y seguir con Capa 0.

---

## Checklist final de Phase 2.5

- [ ] CLAUDE.md versión 2.1 commiteado y vigente
- [ ] `docs/VISION_2_1.md` commiteado como master
- [ ] Canónicas auditadas y marcadas con estado real (`apis_internas.md`, `colecciones_mongo.md`, `eventos.md`)
- [ ] `docs/canonicas/score_engine_contract.md` con schema v1 validado por Iván
- [ ] `docs/canonicas/integraciones_sismo.md` ampliada con 4 endpoints write
- [ ] Fichas de spec creadas para los 4 agentes nuevos (sku_canonicalizer, portfolio, account_intel, pricing_engine)
- [ ] Audit log writers en login, score evaluate, recommendations approve/reject, config changes (Build 2.5.2)
- [ ] Collection `contacts` + endpoints opt-in/out + helper `can_send_proactive` (Build 2.5.3)
- [ ] Compliance Officer Plano 1 vivo + colección `compliance_envelope` con seed (Build 2.5.4)
- [ ] CGO como role nativo + brief_delivery simultáneo CEO+CGO + recommendation approval por role (Build 2.5.5)
- [ ] Score Engine contract test en CI semanal funcionando (Build 2.5.6)
- [ ] APScheduler persistente con MongoDBJobStore (Build 2.5.7)
- [ ] Langfuse self-hosted operativo (Build 2.5.8)
- [ ] Baseline operativo capturado en `argos.roddos.com/baseline` (Build 2.5.8)
- [ ] System User Meta + Service Account Google formalizados (Build 2.5.8)
- [ ] ROG-A6 metadata mutation policy con test guard (Build 2.5.9)
- [ ] Coverage enforced en CI (`--cov-fail-under=80`)
- [ ] DT-004 (scheduler in-memory), DT-025 (audit log) marcadas resueltas en `deuda_tecnica.md`
- [ ] Bitácora `/docs/claude/phase_2.5_alineacion.md` cerrada con decisiones, errores resueltos y aprendizajes
- [ ] Tag `phase-2.5-closed` en el repo

---

## Cuando Phase 2.5 esté cerrada

1. CEO revisa y confirma cierre vía PR de bitácora
2. Claude.ai entrega `.planning/phase_3_prompt.md` (Capa 1 · Foundation WhatsApp + Wava + SISMO write + brief unificado)
3. Bitácora `/docs/claude/phase_3_whatsapp_kyc.md` se reinicializa con la spec de Capa 1
4. Phase 3 inicia con muro de carga firme

---

## Notas para Claude Code

Esta phase es 90% plomería y 10% código nuevo. La tentación va a ser saltarse builds o consolidar varios en uno solo "para ir rápido". **No lo hagas.** Cada Build aquí cierra una ROG incumplida o una deuda concreta; juntarlos pierde la trazabilidad y degrada el muro de carga que Phase 3 necesita.

Si en cualquier punto encuentras una contradicción entre Visión 2.1 y código actual que NO esté contemplada en estos builds, detén el trabajo y abre issue con título `[CLAUDE-md/spec] descripción` para discusión con CEO antes de seguir.

El criterio de éxito de Phase 2.5 no es "tengo todo el checklist marcado". Es "Phase 3 puede arrancar sin heredar deuda silenciosa". Los dos no son lo mismo: el primero se puede falsificar marcando checkboxes a la fuerza; el segundo requiere que cada Build cierre realmente lo que dice cerrar y que la suite de tests refleje el estado correcto.

Phase 2.5 es la última oportunidad de corregir antes de meter código de revenue. Hacelo bien.
