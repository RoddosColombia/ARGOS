"""Tests del Score Engine · reglas duras + cálculo + API · Phase 2."""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import pytest_asyncio
from argos.agents.score.claude_scorer import ClaudeScorer, ClaudeScoreResult
from argos.agents.score.engine import ScoreEngine, ScoreSolicitud
from argos.agents.score.xgboost_scorer import (
    Scorecard,
    XGBoostScorer,
    score_comportamental_to_float,
)
from argos.auth.security import create_access_token
from argos.config import get_settings
from argos.db import collections as col
from argos.db.indexes import ensure_indexes
from argos.main import create_app
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from tests.backend.test_integration_mongo import REAL_URI

# ─── Unit tests (no Mongo) ───────────────────────────────────────────────


class _FakeClaudeScorer(ClaudeScorer):
    """Inyecta un delta y narrativa fijos sin llamar a Anthropic."""

    def __init__(self, *, delta: float = 0.05, fraude: bool = False) -> None:
        self._delta = delta
        self._fraude = fraude
        self._api_key = "fake"
        self._client = None
        self._model = "fake-model"

    @property
    def enabled(self) -> bool:
        return True

    async def analyze(
        self,
        kyc_data: dict[str, Any],
        document_texts: list[str] | None = None,
        partner_data: dict[str, Any] | None = None,
    ) -> ClaudeScoreResult:
        return ClaudeScoreResult(
            delta=self._delta,
            narrativa="test narrativa fija",
            fraude_detectado=self._fraude,
        )


def test_score_comportamental_mapping() -> None:
    assert score_comportamental_to_float("A+") == 1.0
    assert score_comportamental_to_float("E") == 0.1
    assert score_comportamental_to_float(None) == 0.5
    assert score_comportamental_to_float("X") == 0.5  # fallback


def test_xgboost_scorer_pondera_features() -> None:
    sc = Scorecard(
        score_externo=1.0, capacidad_pago=1.0, estabilidad_laboral=1.0,
        score_comportamental=1.0, validacion_biometrica=1.0,
    )
    s = XGBoostScorer().score(sc)
    assert s == pytest.approx(1.0, abs=0.001)
    sc_zero = Scorecard(0.0, 0.0, 0.0, 0.0, 0.0)
    assert XGBoostScorer().score(sc_zero) == pytest.approx(0.0, abs=0.001)


async def test_hard_rule_auco_low_rechaza_sin_llamar_claude() -> None:
    """ROG-S3: si AUCO<70, rechazo inmediato sin invocar Capa 2."""
    fake_claude = _FakeClaudeScorer()
    engine = ScoreEngine(claude=fake_claude)
    sol = ScoreSolicitud(
        solicitud_id="SCR-test-1",
        producto="credito_rodante",
        cedula="80075452",
        nombre="Test User",
        ingreso_declarado=2_000_000,
        gastos_mensuales=1_000_000,
        tipo_empleo="delivery",
        uso_moto="trabajo",
        auco_score=65.0,  # < 70 → rechazo
    )
    result = await engine.evaluate(sol)
    assert result.decision == "rechazado_regla_dura"
    assert result.regla_dura_aplicada is not None
    assert "auco_score" in result.regla_dura_aplicada
    assert result.score_final == 0


async def test_hard_rule_riskseal_fraud_rechaza() -> None:
    engine = ScoreEngine(claude=_FakeClaudeScorer())
    sol = ScoreSolicitud(
        solicitud_id="SCR-test-2", producto="credito_rodante",
        cedula="123", nombre="X", ingreso_declarado=2_000_000, gastos_mensuales=500_000,
        tipo_empleo="empleado", uso_moto="personal",
        riskseal_fraud=True,
    )
    result = await engine.evaluate(sol)
    assert result.decision == "rechazado_regla_dura"
    assert result.regla_dura_aplicada == "riskseal_fraud_flag"


async def test_hard_rule_dti_alto_rechaza() -> None:
    engine = ScoreEngine(claude=_FakeClaudeScorer())
    sol = ScoreSolicitud(
        solicitud_id="SCR-test-3", producto="credito_rodante",
        cedula="123", nombre="X",
        ingreso_declarado=2_000_000, gastos_mensuales=1_500_000,  # DTI = 0.75 > 0.60
        tipo_empleo="empleado", uso_moto="personal",
    )
    result = await engine.evaluate(sol)
    assert result.decision == "rechazado_regla_dura"
    assert "dti" in result.regla_dura_aplicada


async def test_score_calculo_combinado_y_decision_aprobado() -> None:
    """Cliente A+ con buenos partners · combina XGBoost + Claude · debe aprobar."""
    engine = ScoreEngine(claude=_FakeClaudeScorer(delta=0.10))
    sol = ScoreSolicitud(
        solicitud_id="SCR-test-4", producto="credito_rodante",
        cedula="123", nombre="Cliente VIP",
        ingreso_declarado=4_000_000, gastos_mensuales=1_000_000,  # DTI=0.25 → capacidad alta
        tipo_empleo="empleado", uso_moto="personal",
        score_comportamental="A+",  # bypass cliente RODDOS · threshold=400
        auco_score=95.0,
        riskseal_score=0.85,
        palenca_estabilidad_meses=24,
    )
    result = await engine.evaluate(sol)
    assert result.decision == "aprobado"
    assert result.score_final >= 400
    # delta_claude debe estar en rango
    assert -0.15 <= result.delta_claude <= 0.15
    # narrativa de Claude persistida (ROG-S4)
    assert "narrativa" in result.narrativa or len(result.narrativa) > 0


async def test_score_threshold_rdx_leasing_mayor_que_rodante() -> None:
    """credito_rdx_leasing requiere 650 default · más estricto que rodante."""
    engine = ScoreEngine(claude=_FakeClaudeScorer(delta=0.0))
    base = ScoreSolicitud(
        solicitud_id="SCR-test-5",
        producto="credito_rdx_leasing",
        cedula="x", nombre="x",
        ingreso_declarado=3_000_000, gastos_mensuales=1_500_000,
        tipo_empleo="empleado", uso_moto="trabajo",
        auco_score=85.0, riskseal_score=0.6,
    )
    result = await engine.evaluate(base)
    assert result.threshold_aplicado == 650
    # Mismo perfil con score_comportamental="A+" baja a 600
    base.score_comportamental = "A+"
    base.solicitud_id = "SCR-test-5b"
    result_a = await engine.evaluate(base)
    assert result_a.threshold_aplicado == 600


# ─── Integration tests (Mongo + API) ─────────────────────────────────────


pytestmark_integration = pytest.mark.skipif(
    not REAL_URI,
    reason="MONGODB_URI no disponible · integration tests saltados",
)


@pytest_asyncio.fixture
async def indexed_db() -> AsyncIterator[AsyncIOMotorDatabase]:
    client = AsyncIOMotorClient(REAL_URI, serverSelectionTimeoutMS=5000)
    db = client[os.environ.get("MONGODB_TEST_DATABASE", "argos_test")]
    for c in col.ALL_KNOWN:
        await db[c].drop()
    await ensure_indexes(db)
    try:
        yield db
    finally:
        for c in col.ALL_KNOWN:
            await db[c].drop()
        client.close()


def _ceo_token() -> str:
    return create_access_token(subject="ceo@roddos.com", role="ceo", workspace_id="RODDOS")


async def _authed_client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setenv("MONGODB_URI", REAL_URI)
    monkeypatch.setenv("MONGODB_DATABASE", os.environ.get("MONGODB_TEST_DATABASE", "argos_test"))
    monkeypatch.setenv("ARGOS_DISABLE_SCHEDULER", "true")
    get_settings.cache_clear()
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        yield client
    get_settings.cache_clear()


@pytestmark_integration
async def test_evaluate_endpoint_persiste_y_emite_evento(
    indexed_db: AsyncIOMotorDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = {"Authorization": f"Bearer {_ceo_token()}", "X-Workspace-Id": "RODDOS"}
    async for client in _authed_client(monkeypatch):
        resp = await client.post(
            "/api/v1/score/evaluate",
            headers=headers,
            json={
                "producto": "credito_rodante",
                "cedula": "80075452",
                "nombre": "Andrés San Juan",
                "ingreso_declarado": 3_500_000,
                "gastos_mensuales": 1_200_000,
                "tipo_empleo": "delivery",
                "uso_moto": "trabajo",
                "score_comportamental": "A",
                "monto_solicitado": 800_000,
                "auco_score": 90.0,
                "riskseal_score": 0.7,
                "palenca_estabilidad_meses": 12,
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["decision"] in {"aprobado", "rechazado"}
        assert body["score_final"] >= 0

    # Persistido
    docs = await indexed_db[col.SCORING_SOLICITUDES].find({"workspace_id": "RODDOS"}).to_list(length=10)
    assert len(docs) == 1
    # Evento emitido (ROG-S5)
    event = await indexed_db[col.ARGOS_EVENTS].find_one({"event_type": "score.evaluated"})
    assert event is not None
    assert event["producer"] == "score_engine"
    assert event["metadata"]["engine_version"] == get_settings().score_engine_version


@pytestmark_integration
async def test_list_solicitudes_endpoint(
    indexed_db: AsyncIOMotorDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = {"Authorization": f"Bearer {_ceo_token()}", "X-Workspace-Id": "RODDOS"}
    async for client in _authed_client(monkeypatch):
        # Crea 2 evaluaciones
        for n in ("Cliente A", "Cliente B"):
            await client.post(
                "/api/v1/score/evaluate",
                headers=headers,
                json={
                    "producto": "credito_rodante",
                    "cedula": "12345" + str(hash(n) % 100),
                    "nombre": n,
                    "ingreso_declarado": 3_000_000,
                    "gastos_mensuales": 1_000_000,
                    "tipo_empleo": "empleado",
                    "uso_moto": "personal",
                    "monto_solicitado": 500_000,
                },
            )
        # Lista
        resp = await client.get("/api/v1/score/solicitudes?limit=10", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert all("decision" in s for s in body)
        assert all(s["score_final"] >= 0 for s in body)
