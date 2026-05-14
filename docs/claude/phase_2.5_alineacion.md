# Bitácora Phase 2.5 · Alineación y Plomería

> Documento vivo — actualizado al cierre de cada build.
> Refs: `.planning/phase_2.5_prompt.md` · Visión 2.1 · CLAUDE.md

**Estado global:** 7 de 9 builds cerrados · Builds 2.5.8 y 2.5.9 pendientes.

---

## Builds cerrados

### Build 2.5.1 — Alineación documental + canónicas sincronizadas

**Estado:** ✅ Cerrado · 2026-04-29 · Commit `00258ee` / PR #21

**Qué se hizo:**
- CLAUDE.md 2.1 y docs/VISION_2_1.md commiteados como fuente de verdad
- `docs/canonicas/apis_internas.md`, `colecciones_mongo.md`, `eventos.md` auditados con estados `implementado` / `spec·pendiente`
- `docs/canonicas/score_engine_contract.md` creado con schema v1 del Score Engine (campos canónicos, política de cambios, flujo de contrato)
- `docs/canonicas/integraciones_sismo.md` ampliada con 4 endpoints write ARGOS→SISMO (spec, no implementación)
- 4 fichas de agentes nuevas creadas: `sku_canonicalizer.md`, `portfolio.md`, `account_intel.md`, `pricing_engine.md`

**Decisiones tomadas:**
- Score Engine documentado como pass-through, no clon: governance crediticia vive en `roddos-scoring` bajo ownership del CGO (Iván Echeverri)
- Cobranza marcada explícitamente fuera de scope en todas las canónicas (corrección 2.1)

**Deuda generada:** ninguna

---

### Build 2.5.2 — Audit log writers (cierra ROG-A12 + DT-025)

**Estado:** ✅ Cerrado · 2026-04-30 · PR #22

**Qué se hizo:**
- `argos/services/audit.py`: helper `audit_write()` con validación, skip silencioso sin DB, manejo de excepciones, soporte `actor_role` (ROG-G3)
- Call sites integrados: login (success + failure), score evaluate, recommendations approve/reject, config queries CRUD, config categories toggle
- Schema de `audit_log` documentado en canónicas con campo `actor_role` para ROG-G3
- 14 test cases en `tests/backend/test_audit_writer.py` · cobertura ≥90%

**Decisiones tomadas:**
- `actor_role` como campo separado (no dentro de `actor.role` nested) para facilitar queries directas en Mongo
- Skip silencioso si DB no disponible: no bloquea operaciones, loggea warning

**Deuda generada:** ninguna · DT-025 cerrada

---

### Build 2.5.3 — Collection contacts + opt-in registry (cierra ROG-W1)

**Estado:** ✅ Cerrado · PR #23

**Qué se hizo:**
- Colección `contacts` con índices (workspace+phone unique, opt-in marketing/utility, last_message_at)
- Schema completo con `opt_in_marketing` y `opt_in_utility` nested independientes
- 4 endpoints REST: POST opt-in, POST opt-out, GET opt-status, GET contacts (listado)
- Helper `argos.services.opt_in.can_send_proactive(db, workspace_id, phone, type)` que retorna `(allowed: bool, reason: str)`
- Tests coverage ≥85% en módulo opt_in
- Audit trail en cada cambio de opt-in/out

**Decisiones tomadas:**
- opt_in marketing y utility como objetos independientes (no un campo de tipo) por requerimiento Meta 2026 (distintos consentimientos por tipo de comunicación)
- History append-only dentro del objeto para trazabilidad regulatoria

**Deuda generada:** ninguna

---

### Build 2.5.4 — Compliance Officer Plano 1 (cierra ROG-A2 + ROG-A10)

**Estado:** ✅ Cerrado · PR #24

**Qué se hizo:**
- `argos/agents/compliance_officer/service.py`: clase `ComplianceOfficer` con `validate_action()`, `is_within_envelope()`, `get_envelope()`
- `argos/agents/compliance_officer/envelope.py`: lectura de `compliance_envelope` desde Mongo con defaults en seed
- Colección `compliance_envelope` con schema: `action_type`, `envelope: {min, max, unit}`, `plano (1/2/3)`, `approved_by`, `active`
- Seed inicial conservador: `pricing.adjust_meli` ±5%, `bidding.adjust_meta` ±10%, `ad_set.pause` configurable, `creative.suggest` siempre permitido
- 3 endpoints: GET envelope, POST envelope (solo CEO), POST validate
- Tests: `test_compliance_officer.py` dentro/fuera de envelope, escalation a Plano 2/3, audit_log writes

**Decisiones tomadas:**
- `approval_required_role` como campo en cada `recommendation` para enrutar la cola de aprobación (previamente implícito)
- Compliance Officer como agente vivo (no solo spec) · cualquier agente puede llamar `compliance.validate_action()` antes de ejecutar

**Deuda generada:** ninguna

---

### Build 2.5.5 — CGO role nativo + brief delivery simultáneo (cierra ROG-G1 + ROG-G3)

**Estado:** ✅ Cerrado · 2026-05-XX · PR #25

**Qué se hizo:**
- Schema `users` actualizado con role `cgo` como nativo en el enum
- Seed condicional del CGO (Iván Echeverri) vía `CGO_EMAIL`/`CGO_PASSWORD_HASH`/`CGO_WORKSPACE_ID`
- `auth/deps.py`: permisos del role `cgo` — read todos los endpoints, write en approval Plano 2, read-only en Plano 3
- Endpoint `POST /api/v1/recommendations/{id}/approve` valida que el JWT role coincida con `approval_required_role`
- `argos/services/brief_delivery.py`: `send_brief_to_leadership(brief)` entrega idéntico a CEO + CGO simultáneamente (ROG-G1)
- Frontend: Sidebar filtrado por role, página `/approvals` con cola filtrada por Plano
- Tests: `test_cgo_role.py`, `test_brief_delivery.py`, `test_recommendation_approval.py`

**Decisiones tomadas:**
- `approval_required_role` enum: `ceo | cgo | none` — mapeo en el `recommendation`, no calculado en runtime
- CGO ve todo en read (mismo dashboard que CEO) pero su cola de approval solo muestra Plano 2 · CEO ve Plano 2 y 3

**ROGs cerradas:** ROG-G1 (output simultáneo), ROG-G2 (approval por role), ROG-G3 (audit del aprobador)

**Deuda generada:** ninguna

---

### Build 2.5.6 — Score Engine contract test en CI semanal (cierra ROG-S5)

**Estado:** ✅ Cerrado · 2026-05-14 · Commit `23fe07c` / merge `8984dc0` en main (#26)

**Qué se hizo:**
- `tests/contract/test_score_engine_contract.py`: 6 tests de contrato vs schema v1 canónico
  - Valida campos required: `decision`, `score_final`, `solicitud_id`, `engine_version`, `evaluado_en`
  - Valida enum `decision` ∈ {aprobado, rechazado, revision_manual}
  - Valida formato ISO 8601 de `evaluado_en`
  - Valida `engine_version` non-empty
  - Valida `monto_aprobado` presente y >0 cuando `decision == aprobado`
  - Valida que el endpoint responde (no timeout, no 5xx)
  - Auto-skip si `SCORE_ENGINE_API_URL` / `SCORE_ENGINE_API_KEY` no configuradas (seguro en PRs de feature)
- `.github/workflows/contract-tests.yml`: cron lunes 06:00 UTC + `workflow_dispatch`
  - Notifica vía webhook `CONTRACT_TEST_NOTIFY_URL` si falla
  - Flag `notify_on_success` para validación manual
- `pyproject.toml`: marcadores pytest `contract` e `integration` registrados en strict-markers

**Decisiones tomadas:**
- Tests contra endpoint real (no mock) porque el propósito es detectar drift del schema del motor externo
- `pytest.skip()` automático sin env vars: permite que el workflow de CI de PRs de feature no requiera secrets
- Tests aceptan tanto HTTP 200 como 422 como respuestas válidas (422 = regla de negocio violada, no error del schema)
- Contrato tiene su propio workflow separado del CI principal (no bloquea PRs de feature, corre semanal)

**ROG cerrada:** ROG-S5 operativa

**Deuda generada:** ninguna

---

### Build 2.5.7 — APScheduler persistente con MongoDBJobStore (cierra DT-004)

**Estado:** ✅ Cerrado · 2026-05-14 · Commit `c8e9bf0` / merge `de3eb38` en main (#27)

**Qué se hizo:**
- `src/backend/argos/scheduler.py`:
  - Job wrappers refactorizados: eliminado argumento `db: AsyncIOMotorDatabase` (no picklable con pickle de APScheduler); usan `_db` variable de módulo
  - `MongoDBJobStore` configurado cuando `MONGODB_URI` está disponible: `host=MONGODB_URI`, `collection="apscheduler_jobs"`
  - Fallback automático a `MemoryJobStore` explícito cuando `MONGODB_URI` vacío (dev sin DB, tests unitarios)
  - `misfire_grace_time` explícito: `MISFIRE_GRACE_DAILY=60s` (jobs 6h, 12h, daily), `MISFIRE_GRACE_FREQUENT=300s` (jobs 1h, 30min)
  - `start_scheduler()` lee `settings.mongodb_uri` para decidir jobstore
- `tests/backend/test_scheduler.py`: 11 tests (vs 4 anteriores)
  - `test_build_scheduler_registers_all_expected_jobs`: verifica los 13 jobs exactos
  - `test_build_scheduler_misfire_grace_daily/frequent`: verifica config por clase de job
  - `test_build_scheduler_uses_memory_jobstore_without_uri`: MemoryJobStore cuando no hay URI
  - `test_build_scheduler_uses_mongo_jobstore_with_uri`: MongoDBJobStore con `StubMongoJobStore` (hereda `BaseJobStore` para pasar isinstance de APScheduler)
  - `test_jobs_take_no_db_argument`: garantiza `job.args == ()` en todos los jobs (pickle compat)
  - `test_jobs_survive_scheduler_restart`: integración (skip sin `MONGODB_URI` real)
- `docs/canonicas/colecciones_mongo.md`: `apscheduler_jobs` marcada implementada + schema completo + nota de implementación
- `docs/claude/deuda_tecnica.md`: DT-004 marcada resuelta

**Decisiones tomadas:**
- Variable de módulo `_db` en lugar de argumento: trade-off de acoplamiento implícito aceptado porque APScheduler requiere callables picklables y `AsyncIOMotorDatabase` no lo es. El scheduler siempre corre en el mismo proceso donde `_db` está inicializado — el acoplamiento es local, no cross-process.
- `MemoryJobStore` explícito (no implícito de APScheduler): mejora testabilidad y debugging
- `StubMongoJobStore(BaseJobStore)` en tests: necesario porque APScheduler valida `isinstance(jobstore, BaseJobStore)` al construir el scheduler — MagicMock no pasa el check.
- `misfire_grace_time` diferenciado por frecuencia del job: un job que corre cada 30min tiene más contexto de urgencia que uno daily, y 300s de gracia es más relevante para jobs de notificación frecuente.

**Deuda generada:** ninguna · DT-004 cerrada

---

## Builds pendientes

### Build 2.5.8 — Builds 0.6-0.9 cleanup (Langfuse + baseline + credenciales)

**Estado:** 🟡 Pendiente

**Pendiente:**
- Build 0.7: Langfuse self-hosted en Render con PostgreSQL
- Build 0.8: Formalización System User Meta + Service Account Google
- Build 0.9: Captura baseline operativo en colección `system_health` + vista `/baseline`

**Bloqueos:** ninguno técnico · requiere decisiones de infra del CEO (Render config, BM RODDOS, MCC RODDOS)

---

### Build 2.5.9 — ROG-A6 metadata mutation policy formalizada

**Estado:** 🟡 Pendiente

**Decisión pendiente:** Path A (legalizar mutación con test guard) vs Path B (colección colateral `notifications_dispatch_log`). Recomendación actual: Path A en Phase 2.5.

---

## Errores encontrados durante Phase 2.5

### Error · APScheduler + AsyncIOMotorDatabase no picklable

**Detectado en:** Build 2.5.7 (2026-05-14)
**Contexto:** Al migrar a MongoDBJobStore, los tests fallaban porque `AsyncIOMotorDatabase` (pasado como `args=[db]` a cada job) no es picklable. APScheduler 3.x serializa jobs con pickle para persistir en MongoDB.
**Resolución:** Refactorizar a variable de módulo `_db`. Test adicional `test_jobs_take_no_db_argument` para garantizar que no se regrese a `args=[db]` en el futuro.

### Error · MagicMock no pasa isinstance(BaseJobStore)

**Detectado en:** Build 2.5.7 (2026-05-14) · test `test_build_scheduler_uses_mongo_jobstore_with_uri`
**Contexto:** APScheduler valida tipos en el constructor: `raise TypeError("Expected job store instance or dict for jobstores['default'], got MagicMock")`.
**Resolución:** Crear `StubMongoJobStore(BaseJobStore)` que implementa los métodos abstractos pero registra las llamadas al constructor.

---

## ROGs cerradas en Phase 2.5

| ROG | Build | Estado |
|-----|-------|--------|
| ROG-A12 · audit_log writers | Build 2.5.2 | ✅ |
| ROG-W1 · opt-in registry | Build 2.5.3 | ✅ |
| ROG-A2 · spending caps en código | Build 2.5.4 | ✅ |
| ROG-A10 · Compliance Officer veto | Build 2.5.4 | ✅ |
| ROG-G1 · output simultáneo CEO+CGO | Build 2.5.5 | ✅ |
| ROG-G2 · approval por role | Build 2.5.5 | ✅ |
| ROG-G3 · audit del aprobador | Build 2.5.5 | ✅ |
| ROG-S5 · contract test semanal | Build 2.5.6 | ✅ |

---

## Deuda técnica cerrada en Phase 2.5

| ID | Título | Build |
|----|--------|-------|
| DT-025 | audit_log writers ausentes | Build 2.5.2 |
| DT-004 | APScheduler in-memory | Build 2.5.7 |

---

## Checklist de Phase 2.5

- [x] CLAUDE.md versión 2.1 commiteado y vigente
- [x] `docs/VISION_2_1.md` commiteado como master
- [x] Canónicas auditadas con estado real (`apis_internas.md`, `colecciones_mongo.md`, `eventos.md`)
- [x] `docs/canonicas/score_engine_contract.md` schema v1 (pendiente validación formal de Iván)
- [x] `docs/canonicas/integraciones_sismo.md` ampliada con 4 endpoints write
- [x] Fichas de spec 4 agentes nuevos (sku_canonicalizer, portfolio, account_intel, pricing_engine)
- [x] Audit log writers en login, score evaluate, recommendations approve/reject, config changes
- [x] Collection `contacts` + endpoints opt-in/out + helper `can_send_proactive`
- [x] Compliance Officer Plano 1 vivo + colección `compliance_envelope` con seed
- [x] CGO como role nativo + brief_delivery simultáneo CEO+CGO + recommendation approval por role
- [x] Score Engine contract test en CI semanal funcionando
- [x] APScheduler persistente con MongoDBJobStore
- [ ] Langfuse self-hosted operativo (Build 2.5.8)
- [ ] Baseline operativo en `argos.roddos.com/baseline` (Build 2.5.8)
- [ ] System User Meta + Service Account Google formalizados (Build 2.5.8)
- [ ] ROG-A6 metadata mutation policy con test guard (Build 2.5.9)
- [x] Coverage enforced en CI (`--cov-fail-under=80`) — enforced en módulos críticos
- [x] DT-004 y DT-025 marcadas resueltas en `deuda_tecnica.md`
- [ ] Bitácora cerrada con decisiones, errores y aprendizajes ← (este archivo, cierre definitivo pendiente Builds 2.5.8+2.5.9)
- [ ] Tag `phase-2.5-closed` en el repo ← (después de cerrar 2.5.8+2.5.9)
