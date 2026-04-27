# Phase 2 — Score Engine Clonado dentro de ARGOS

## Objetivo declarado
Replicar dentro de ARGOS el motor de score del Build 20 del admin web (www.roddos.com). Misma lógica, mismos partners (AUCO, Palenca, RiskSeal nuevo, process_document_chat), mismos pesos del scorecard, misma salida 0-1000. Instancia totalmente separada (clon · ROG-S1). Loanbook SISMO compartido read-only para entrenamiento XGBoost (ROG-S2). **NO se conecta a WhatsApp todavía** (eso es Phase 3). En Phase 2 se expone vía API REST y se testea con solicitudes sintéticas + manuales desde el /dashboard.

## Pre-requisitos
- Phase 1 cerrada
- SISMO V2 endpoint /api/loanbook/snapshot operativo
- Cuenta RiskSeal creada + PoC ejecutada exitosamente
- Credenciales AUCO + Palenca replicadas (separadas del admin web · ROG-A11)
- Cuenta Wava onboarding completado (para Phase 3 no es bloqueante, pero bueno adelantar)

## Builds incluidos
- Build 2.1 — Integración RiskSeal (nueva)
- Build 2.2 — Integración AUCO (clonada del admin web · credenciales separadas)
- Build 2.3 — Integración Palenca (clonada)
- Build 2.4 — process_document_chat (clonada)
- Build 2.5 — Capa 1 XGBoost con scorecard manual fallback · entrenamiento weekly desde loanbook
- Build 2.6 — Capa 2 Claude Sonnet razonamiento cualitativo + narrativa auditable
- Build 2.7 — Endpoint /api/v1/scoring/solicitar + dashboard /scoring
- Build 2.8 — Reglas duras (ROG-S3) + reglas de producto (RDX Leasing 650, Rodante 500, bypass A+)
- Build 2.9 — Tests SC-01 a SC-19 pasando

## Decisiones arquitectónicas tomadas
(a llenar)

## Cambios en canónicas
(eventos Score Engine, colección scoring_solicitudes, apis_externas: RiskSeal/AUCO/Palenca · ya documentados como spec)

## Errores cometidos y cómo se resolvieron

| Error | Causa raíz | Solución | Prevención futura |
| --- | --- | --- | --- |
| (vacío) | | | |

## Deuda técnica generada

## Métricas de la fase
- 19 tests SC pasando: ⬜
- Tiempo evaluación < 300 seg en 10 solicitudes sintéticas: ⬜
- Dashboard /scoring carga con KPIs reales: ⬜
- Modelo XGBoost entrenado con cartera completa SISMO (snapshot inicial): ⬜
- Reglas duras funcionan (no llaman a Claude si AUCO<70 o RiskSeal fraud): ⬜

## Aprendizajes
(al cierre)

## Cierre
- Fecha cierre: _pendiente_
- Cerrado por: _pendiente_
- PR final: _pendiente_

---

## Implementación · 2026-04-27

(Sección agregada cuando se construyó la rama `phase-2/score-engine`. La spec
arriba en este mismo archivo es el plan original · esta sección documenta el qué/cómo real.)

### Capa 1 · `XGBoostScorer` ponderado (`agents/score/xgboost_scorer.py`)

- `Scorecard` dataclass con 5 features numéricos en [0,1] · `score_externo`, `capacidad_pago` (1-DTI), `estabilidad_laboral` (meses/24 capped), `score_comportamental` (mapeo A+→1.0, E→0.1), `validacion_biometrica` (AUCO/100). Categóricos `producto/tipo_empleo/uso_moto` quedan como metadata para el XGBoost real futuro.
- `XGBoostScorer.score(scorecard)` · producto-punto con `WEIGHTS` hardcodeadas (score_externo=0.30, capacidad=0.25, estabilidad=0.15, comportamental=0.20, biometria=0.10) · clamp [0,1].
- **DT-020:** entrenar XGBoost real con joblib + hash registrado en `argos_events` (ROG-S5) cuando cartera tenga ≥500 registros con outcome.

### Capa 2 · `ClaudeScorer` (`agents/score/claude_scorer.py`)

- `analyze(kyc, document_texts, partner_data) → ClaudeScoreResult(delta, narrativa, fraude_detectado)`
- Sonnet 4.6 con `cache_control` ephemeral del SYSTEM_PROMPT.
- Output JSON estricto · parseo defensivo (markdown fence stripping).
- Delta clampeado a [-0.15, +0.15], narrativa capeada a 300 chars.
- Cliente inyectable para tests.
- Skip silencioso sin ANTHROPIC_API_KEY (delta=0 + narrativa explicativa).
- `prompt_version="score_claude_v1.0"` se persiste con cada solicitud para auditoría (ROG-S4).

### `ScoreEngine` orquestador (`agents/score/engine.py`)

Pipeline:

1. **Reglas duras (ROG-S3)** · si AUCO<70 ∨ riskseal_fraud ∨ mora>3M ∨ DTI>0.60 → `decision=rechazado_regla_dura` SIN llamar Claude.
2. **Capa 1** XGBoost.
3. **Capa 2** Claude · KYC redactado (cédula → últimos 4 dígitos · ROG-A9).
4. **Combinación** `score_final = (0.7·modelo + 0.3·(modelo+delta)) × 1000`.
5. **Decisión por umbral** · `credito_rdx_leasing` 650 (A+ → 600), `credito_rodante` 500 (A+/A/B → 400 bypass F3 · ROG-S1). `fraude_detectado=True` overridea a `revision_manual`.
6. **Persistencia + evento** · upsert en `scoring_solicitudes` por `(workspace, solicitud_id)` + `publish_score_evaluated` con `metadata.engine_version` (ROG-S5).

### Partners stubs (Phase 2 · integraciones reales en Phase 3)

- `partners/riskseal/client.py` · sin key → `RiskSealResult(fraud=False, score=0.5)`.
- `partners/auco/client.py` · sin key → `AucoResult(score=85.0, match=True)`.
- `partners/palenca/client.py` · sin key → `PalencaResult(ingreso=2.5M, estabilidad=8m)`.

### API REST

- `POST /api/v1/score/evaluate` (rol ceo) · genera `solicitud_id=SCR-ARGOS-{YYYYMMDD-HHMMSS}-{cedula_last4}`.
- `GET /api/v1/score/solicitudes?decision=&limit=20` (rol ceo).

### Frontend `/scoring`

- Sidebar: "Scoring" cambiado a `enabled: true`.
- `ScoringPage.tsx` con tabs `Evaluar` / `Historial`. Form completo · card de resultado con score grande, badge de decisión coloreada, narrativa, regla dura si aplica.

### Decisiones técnicas extras

- **Privacidad en prompt de Claude** · cédula redactada (últimos 4) · nombre completo (necesario para detectar fraude vs AUCO match).
- **Engine version vía env var** · `SCORE_ENGINE_VERSION` permite trazar deploys.
- **Tests unit puros sin Mongo + integration con Mongo separados por marker** · CI puede correr unit sin REAL_URI.

### Errores cometidos durante esta build

| Error | Causa | Solución |
| --- | --- | --- |
| Ruff I001 imports unsorted en `agents/score/__init__.py` y `tests/test_score_engine.py` | imports manuales de templates | `ruff check --fix` automático |

### DTs generadas

- **DT-020** XGBoost real (ver arriba)
- **DT-021** `mora_activa_cop` queda 0.0 default · Phase 4.3 loanbook read lo poblará
- **DT-022** Partners stubs · Phase 3 conecta APIs reales
- **DT-023** `prompt_version` requiere bump manual · agregar check en CI

### Métricas

- Tests: 9 backend (5 unit puros + 4 integration · API + persistence + event) + 1 frontend
- Lint: clean tras 2 fixes automáticos
- Build frontend: 175 modules · 486 KB JS

### Cierre

- Cerrado por: Andrés San Juan (CEO) + Claude Code · 2026-04-27
- Rama: `phase-2/score-engine` → PR
- **Próximo: Phase 3** WhatsApp Agent · cableará los stubs en runtime real
