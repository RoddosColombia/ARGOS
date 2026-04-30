# docs/canonicas/score_engine_contract.md

Contrato canónico de la API del Score Engine externo (`https://github.com/RoddosColombia/roddos-scoring`).

> **Creado en Phase 2.5 · Build 2.5.1 (2026-04-29)** como cierre de ROG-S5.
> Owner del repo: Iván Echeverri (CGO).
> Owner del contrato (lado ARGOS): mantenido en este archivo, validado vía test de contrato semanal en CI.
> Cualquier cambio breaking del Score Engine → coordinar con CGO antes del deploy → bump de `version` acá.

## Versión vigente

**v1** · vigente desde 2026-04-27 (cierre del pivote Phase 2 a pass-through).

## Principio operativo

ARGOS es pass-through. NO ejecuta lógica crediticia, NO aplica reglas duras (ROG-S3), NO llama Claude para narrativa. Reenvía el payload tal cual al endpoint `/v1/evaluate` del Score Engine externo, recibe el response, lo persiste en `audit_log` propio (ROG-S4), y lo entrega al consumidor (WhatsApp Agent en Capa 1).

## Endpoint

```
POST {SCORE_ENGINE_API_URL}/v1/evaluate
Authorization: Bearer {SCORE_ENGINE_API_KEY}
Content-Type: application/json
```

## Schema de request (v1)

ARGOS no valida el schema del request — lo reenvía tal cual viene del WhatsApp Agent o del frontend de pruebas. La validación canónica del payload de entrada vive en el repo `roddos-scoring`. Spec referencial:

```json
{
  "workspace_id": "RODDOS",
  "origen": "argos_whatsapp",
  "producto": "credito_repuestos | credito_moto | ambos",
  "monto_solicitado": 250000,

  "datos_personales": {
    "nombre_completo": "string",
    "email": "string",
    "telefono": "string E.164",
    "fecha_nacimiento": "YYYY-MM-DD",
    "tipo_documento": "CC | CE | Pasaporte",
    "numero_documento": "string",
    "lugar_expedicion": "string",
    "lugar_nacimiento": "string"
  },

  "residencia": {
    "departamento": "string",
    "ciudad": "string",
    "direccion": "string",
    "zona": "string"
  },

  "actividad_economica": {
    "tipo_empleo": "empleado | independiente | delivery | mototaxi",
    "plataforma_delivery": "string nullable",
    "rango_salarial": "string",
    "gastos_mensuales": "number",
    "tiempo_actividad_meses": "number",
    "uso_moto": "string"
  },

  "documentos": [
    {"tipo": "cedula | desprendible | extracto_bancario", "url": "string"}
  ],

  "referencia": {
    "nombre": "string",
    "telefono": "string",
    "direccion": "string"
  },

  "context": {
    "es_cliente_roddos": "bool",
    "score_comportamental_argos": "A+ | A | B | C | D | E | null",
    "monto_actualmente_aprobado": "number nullable"
  }
}
```

## Schema de response (v1) — CANONICAL · validado por contract test

```json
{
  "decision": "aprobado | rechazado | revision_manual",
  "score_final": 0,
  "solicitud_id": "SCR-ARGOS-2026-XXXX",
  "engine_version": "string · ej. xgb_v2.1_hash_a1b2c3d4",
  "narrativa": "string · razonamiento auditable Claude · puede estar vacía si decisión por regla dura",
  "regla_dura_aplicada": "string nullable · ej. 'auco_score<70' o null si pasó reglas duras",
  "categoria_riesgo": "muy_bajo | bajo | medio | alto | muy_alto",
  "monto_aprobado": "number nullable · null si decision != aprobado",
  "score_modelo": "number 0.0-1.0 · output XGBoost crudo",
  "score_claude": "number -0.15 to 0.15 · ajuste cualitativo",
  "tiempo_evaluacion_seg": "number",

  "partners_consultados": {
    "auco": {"estado": "ok | error | skipped", "score_biometrico": "number nullable", "latency_ms": "number"},
    "riskseal": {"estado": "ok | error | skipped", "digital_score": "number nullable", "fraud_flag": "bool", "latency_ms": "number"},
    "palenca": {"estado": "ok | error | skipped | not_applicable", "ingreso_verificado": "number nullable", "latency_ms": "number"}
  },

  "umbral_aplicado": "number · ej. 400 si bypass, 500 normal, 650 si moto",
  "bypass_aplicado": "bool",
  "evaluado_en": "ISO 8601 UTC"
}
```

### Campos REQUIRED (validados por contract test)

- `decision` (enum)
- `score_final` (number)
- `solicitud_id` (string non-empty)
- `engine_version` (string non-empty)
- `evaluado_en` (ISO 8601)

### Campos OPTIONAL (presencia condicional)

- `monto_aprobado` requerido sólo si `decision == "aprobado"`
- `regla_dura_aplicada` puede ser null si pasó reglas duras
- `narrativa` puede ser vacía si decisión por regla dura
- `partners_consultados.*` puede tener estado `skipped` si no aplica al producto

## Códigos de respuesta HTTP

| Status | Caso | Acción ARGOS |
|--------|------|--------------|
| 200 | Evaluación exitosa | Persistir en audit_log + devolver response al consumer |
| 400 | Payload malformado | Devolver error al consumer · NO retry · audit_log con `decision=rechazo_payload` |
| 401 | Auth inválida | Bug en config ARGOS · log error severo · alerta operativa |
| 422 | Reglas de negocio violadas (ej. monto > tope producto) | Devolver al consumer con detalle del error · audit |
| 429 | Rate limit del Score Engine | Retry con backoff · si persiste, devolver "evaluación pendiente" al cliente |
| 500-503 | Error transient del Score Engine | 1 retry automático en `ScoreEngineClient` · si persiste, política de degradación (ROG-S3) |
| 504 | Timeout | Idem 500 |

## Política de degradación (ROG-S3)

Si el Score Engine está caído o devuelve error persistente:

1. ARGOS **NO** aprueba ningún crédito sin score (no hay fallback offline).
2. WhatsApp Agent responde al cliente: "estamos validando tu solicitud, te confirmamos en la próxima hora" (no expone error técnico).
3. Solicitud queda en cola persistida `pending_score_evaluations` con retry exponencial cada 15 minutos hasta 4h.
4. Si después de 4h no hay respuesta, escalamiento a operador humano vía notificación interna.
5. Mientras el motor está caído, los flujos cash (F4 cash, ventas sin crédito) **siguen procesando normalmente**. La degradación se contiene al flujo crediticio.

## Audit local lado-ARGOS (cumple ROG-S4 + ROG-A12)

Cada llamada al Score Engine se persiste en `audit_log` con:

```json
{
  "_id": "ULID",
  "workspace_id": "RODDOS",
  "timestamp": "ISO 8601 UTC",
  "actor": {"role": "sistema | cgo | analista", "user_id": "string", "source": "whatsapp_agent | frontend_test | api_direct"},
  "action": "score.evaluate.requested",
  "target": {"solicitud_id": "string · si presente en response"},
  "metadata": {
    "payload_hash": "string · hash del payload sin PII para correlación",
    "decision": "string",
    "score_final": "number",
    "engine_version": "string",
    "latency_ms": "number",
    "http_status": "number"
  }
}
```

Importante: el `payload` completo NO se persiste en `audit_log` por ROG-A9 (PII de terceros / cliente). Solo el hash + metadata derivada.

## Validación continua · contract test semanal en CI

### Workflow `.github/workflows/contract-tests.yml` (creado en Build 2.5.6)

```yaml
name: Contract Tests
on:
  schedule:
    - cron: '0 6 * * 1'  # lunes 06:00 UTC
  workflow_dispatch:
jobs:
  score-engine-contract:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - name: Install
        run: pip install -e ".[dev]"
      - name: Run contract test
        env:
          SCORE_ENGINE_API_URL: ${{ secrets.SCORE_ENGINE_API_URL }}
          SCORE_ENGINE_API_KEY: ${{ secrets.SCORE_ENGINE_API_KEY }}
        run: pytest tests/contract/test_score_engine_contract.py -v
      - name: Notify on failure
        if: failure()
        run: |
          curl -X POST ${{ secrets.CONTRACT_TEST_NOTIFY_URL }} \
            -d '{"text": "Score Engine contract test FAILED · revisar schema vs roddos-scoring"}'
```

### Test reference (`tests/contract/test_score_engine_contract.py`)

```python
"""Test de contrato vs Score Engine externo (roddos-scoring).

Lee schema canonical desde docs/canonicas/score_engine_contract.md, envía payload
de prueba al endpoint /v1/evaluate real, valida que el response cumple campos
required del schema vigente. Si falla, alerta antes de que rompa producción.
"""
import os
import httpx
import pytest

REQUIRED_RESPONSE_FIELDS = {
    "decision": str,
    "score_final": (int, float),
    "solicitud_id": str,
    "engine_version": str,
    "evaluado_en": str,
}

VALID_DECISIONS = {"aprobado", "rechazado", "revision_manual"}

@pytest.mark.contract
def test_score_engine_response_schema_v1():
    base_url = os.environ["SCORE_ENGINE_API_URL"]
    api_key = os.environ["SCORE_ENGINE_API_KEY"]

    payload = {
        "workspace_id": "CONTRACT_TEST",
        "origen": "argos_contract_test",
        "producto": "credito_repuestos",
        "monto_solicitado": 100000,
        "datos_personales": {"nombre_completo": "Test User", "telefono": "+573001234567"},
        "context": {"es_cliente_roddos": False},
    }

    resp = httpx.post(
        f"{base_url}/v1/evaluate",
        json=payload,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30.0,
    )
    assert resp.status_code in (200, 422), f"unexpected status {resp.status_code}"
    data = resp.json()

    for field, expected_type in REQUIRED_RESPONSE_FIELDS.items():
        assert field in data, f"required field missing: {field}"
        assert isinstance(data[field], expected_type), f"field {field} wrong type"

    assert data["decision"] in VALID_DECISIONS
    assert data["score_final"] >= 0
    assert len(data["engine_version"]) > 0
```

## Procedimiento de cambio del contrato

Si Iván necesita cambiar el schema del response (agregar campo, renombrar, eliminar):

1. **Cambio non-breaking** (agregar campo opcional): se puede hacer sin coordinación previa, pero **debe actualizarse este archivo** dentro de la misma semana del deploy.
2. **Cambio breaking** (renombrar, eliminar, cambiar tipo): coordinación obligatoria CEO+CGO antes del deploy. Bump a `v2` acá. Periodo de coexistencia v1+v2 mínimo 30 días para que ARGOS adapte sus consumers.
3. Cualquier deploy del Score Engine que cambie `engine_version` debe registrarse en `docs/claude/score_engine_changelog.md` (crear si no existe) con fecha + diff de pesos del XGBoost si aplica.

## Variables de entorno relacionadas (lado ARGOS)

| Variable | Uso | Quién la setea |
|----------|-----|----------------|
| `SCORE_ENGINE_API_URL` | Base URL del Score Engine | CEO en Render env vars |
| `SCORE_ENGINE_API_KEY` | Bearer token | CEO en Render env vars |
| `RODDOS_MONGODB_URI` | Cluster compartido para read-only de `scoring_solicitudes` | CEO en Render env vars |
| `RODDOS_MONGODB_DATABASE` | Database name (default `roddos_comercial`) | CEO en Render env vars |
| `CONTRACT_TEST_NOTIFY_URL` | Webhook Slack/email para notificar fallas del contract test | CEO + CGO |

## Cambios al contrato

| Versión | Fecha | Cambio | Aprobado por |
|---------|-------|--------|--------------|
| v1 | 2026-04-27 | Versión inicial · pivote a pass-through | CEO + CGO |
| v1 | 2026-04-29 | Documentación formal del contrato (Phase 2.5 Build 2.5.1) | CEO |

## Próximos pasos · Phase 2.5

- [ ] **Build 2.5.6**: implementar `tests/contract/test_score_engine_contract.py` y workflow CI
- [ ] **Build 2.5.6**: configurar `CONTRACT_TEST_NOTIFY_URL` en GitHub Secrets
- [ ] **Validación con Iván**: confirmar que el schema v1 documentado acá refleja la realidad de `roddos-scoring` actual. Si hay drift, actualizar este archivo antes del Build 2.5.6.
