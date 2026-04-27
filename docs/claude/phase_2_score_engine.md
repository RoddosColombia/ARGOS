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

## Corrección arquitectónica · 2026-04-27

**Decisión del CEO**: el Score Engine pasa a ser un repo independiente operado
por Iván, separado de ARGOS. ARGOS NO ejecuta scores.

**Razón**: separación clean de dominios — el motor de score se desarrolla,
versiona y despliega en su propio ciclo (importante porque cambios en pesos
del XGBoost o reglas duras requieren governance crediticia distinta del ciclo
de inteligencia de mercado de ARGOS). El admin web (www.roddos.com) y ARGOS
ahora consumen el mismo motor en lugar de mantener clones separados.

### Cambios en la rama `phase-2/score-engine-readonly`

**Eliminado** (vs la rama `phase-2/score-engine` que NO se mergeó a main):
- `agents/score/xgboost_scorer.py`
- `agents/score/claude_scorer.py`
- `agents/score/engine.py`
- `api/v1/score.py` (versión que ejecutaba el score)
- `db/collections.py` línea `SCORING_SOLICITUDES` (la colección ya no es de ARGOS)
- `db/indexes.py` índices de `scoring_solicitudes`
- `db/events.py` `publish_score_evaluated` (lo emite el repo de Iván en su bus)

**Agregado**:
- `agents/score/reader.py` · `ScoreReader` lee desde `RODDOS_MONGODB_URI` DB `roddos_comercial` colección `scoring_solicitudes`. Skip silencioso sin URI. Multi-tenant filtra por `workspace_id` (ROG-A3 propaga aún cuando el writer es otro).
- `agents/score/client.py` · `ScoreEngineClient` POST a `SCORE_ENGINE_API_URL/v1/evaluate` con `Authorization: Bearer {SCORE_ENGINE_API_KEY}` · timeout 10s · 1 retry · skip silencioso sin URL.
- `api/v1/score.py` reescrito como pass-through:
  - `POST /api/v1/score/evaluate` reenvía payload tal cual al Score Engine externo y devuelve respuesta cruda
  - `GET /api/v1/score/solicitudes` lee del shared DB
  - `GET /api/v1/score/config` expone URL del Score Engine para banner del frontend
- `partners/{riskseal,auco,palenca}/client.py` · stubs sin cambios; quedan disponibles para que el WhatsApp Agent los invoque en Phase 3 durante el flujo de cotización (preview de fraude/biometría/ingresos antes de mandar al Score Engine real).

**Frontend**:
- `ScoringPage.tsx` agrega banner que muestra el `SCORE_ENGINE_API_URL` configurado · empty state mejorado en historial cuando `RODDOS_MONGODB_URI` no está set.
- Sidebar Scoring `enabled: true`.

**Config + .env.example**:
- Nuevas vars: `RODDOS_MONGODB_URI`, `RODDOS_MONGODB_DATABASE` (default `roddos_comercial`), `SCORE_ENGINE_API_URL`, `SCORE_ENGINE_API_KEY`.
- Eliminadas (de la rama anterior NO mergeada): `RISKSEAL_API_KEY/AUCO_API_KEY/PALENCA_API_KEY/SCORE_ENGINE_VERSION` — mantenidas conceptualmente: las de partners siguen existiendo en el repo de Iván · `SCORE_ENGINE_VERSION` ahora se reporta dentro del response del Score Engine externo (campo `engine_version` en `scoring_solicitudes`).

### Decisiones técnicas de la corrección

- **`ScoreReader` no usa el cluster ARGOS** · construye su propio `AsyncIOMotorClient` con `RODDOS_MONGODB_URI`. Conexión lazy (solo abre cuando se llama un método). Cierra explícitamente al final de cada request del API.
- **`ScoreEngineClient.evaluate(client=...)` permite inyectar httpx.AsyncClient** · indispensable para tests con MockTransport. Cuando se pasa, `ScoreEngineClient` no abre/cierra el client (caller es dueño).
- **Pass-through preserva campos del response** · ARGOS NO altera el schema del response del Score Engine. Solo asegura que `decision`, `score_final`, `solicitud_id` estén presentes (con defaults si el upstream omite). El frontend muestra el JSON tal cual.
- **Retry policy: 1 retry en 5xx, 0 en 4xx** · 4xx es error del cliente (payload malformado), no del Score Engine. 5xx es transient · 1 retry con timeout corto (10s) limita el blast radius a 20s en peor caso.

### Tests reescritos

- 4 backend `test_score_engine.py` corrección arquitectónica:
  - `test_client_skip_silencioso_sin_url`
  - `test_client_forward_payload_y_parsea_respuesta` (httpx.MockTransport)
  - `test_client_4xx_levanta_error`
  - `test_client_5xx_reintenta_y_levanta_si_persiste`
- 1 backend `test_reader_skip_silencioso_sin_uri`
- 2 backend integration con shared DB (Mongo real, DB separada `argos_test_roddos_shared`):
  - `test_reader_lee_solicitudes_filtradas_por_workspace` (verifica ROG-A3 cross-workspace)
  - `test_reader_get_by_id`
- 1 backend integration end-to-end:
  - `test_api_evaluate_pass_through_y_solicitudes_lee_shared_db`
- 1 frontend (`ScoringPage.test.tsx`): banner config + form submit + render de result

Total: 8 backend + 1 frontend = 9 nuevos · suite full pasando.

### Errores cometidos durante esta corrección

| Error | Causa | Solución |
| --- | --- | --- |
| Frontend test: `getByText(/score-engine\.roddos\.com/)` no matchea texto adentro de `<code>` | DOM testing-library `getByText` busca match exacto en text node del elemento, no descendientes | Cambiado a `waitFor + banner.textContent.toContain(...)` que itera el árbol |

### DTs activas tras la corrección

- **DT-024 · Frontend no renderiza KYC details enriquecidos** · El response del Score Engine externo puede traer campos extra (partners breakdowns, scorecard features) que ARGOS pasa sin procesar. El frontend actualmente solo muestra los canónicos. Cuando Iván defina el schema final, expandir `ScoreEvaluateResponse` y los componentes.
- **DT-025 · ARGOS no audita las llamadas a /evaluate** · Pass-through actual no escribe a `audit_log` (ROG-A12). Aceptable porque el Score Engine externo audita en su propio side. Si auditoría dual es requerida, agregar middleware logging.

### Cierre de la corrección

- Cerrado por: Andrés San Juan (CEO) + Claude Code · 2026-04-27
- Rama: `phase-2/score-engine-readonly` → PR
- **Próximo: Phase 3** WhatsApp Agent · invoca el ScoreEngineClient real durante el flujo de cotización + crédito.
