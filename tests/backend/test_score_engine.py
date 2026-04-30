"""Tests del Score Engine externo · ARGOS pass-through + reader · Phase 2.

Después de la corrección arquitectónica 2026-04-27, ARGOS no ejecuta scores.
Estos tests validan:
- ScoreEngineClient: skip silencioso · forwarding HTTP · 4xx/5xx error handling.
- ScoreReader: skip silencioso · query a DB compartida (mock).
- API endpoints: forward correcto + lectura desde reader.
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
import pytest_asyncio
from argos.agents.score.client import ScoreEngineClient, ScoreEngineError, ScoreEngineResponse
from argos.agents.score.reader import ScoreReader
from argos.auth.security import create_access_token
from argos.config import get_settings
from argos.main import create_app
from motor.motor_asyncio import AsyncIOMotorClient

from tests.backend.test_integration_mongo import REAL_URI

# ─── ScoreEngineClient ────────────────────────────────────────────────────


async def test_client_skip_silencioso_sin_url() -> None:
    client = ScoreEngineClient(base_url="", api_key="")
    resp = await client.evaluate({"cedula": "x", "nombre": "y"})
    assert isinstance(resp, ScoreEngineResponse)
    assert resp.decision == "no_configurado"
    assert resp.score_final == 0


async def test_client_forward_payload_y_parsea_respuesta() -> None:
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["url"] = str(req.url)
        captured["auth"] = req.headers.get("authorization")
        captured["body"] = req.read().decode("utf-8")
        return httpx.Response(
            200,
            json={
                "decision": "aprobado",
                "score_final": 720,
                "solicitud_id": "SCR-EXTERNAL-1",
                "narrativa": "from external engine",
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://score.test",
        headers={"Authorization": "Bearer fake"},
    ) as inner:
        client = ScoreEngineClient(base_url="https://score.test", api_key="fake")
        resp = await client.evaluate({"cedula": "123", "nombre": "Test"}, client=inner)

    assert resp.decision == "aprobado"
    assert resp.score_final == 720
    assert resp.solicitud_id == "SCR-EXTERNAL-1"
    assert "/v1/evaluate" in captured["url"]
    assert captured["auth"] == "Bearer fake"
    assert "cedula" in captured["body"]


async def test_client_4xx_levanta_error() -> None:
    transport = httpx.MockTransport(
        lambda req: httpx.Response(400, text="bad request")
    )
    async with httpx.AsyncClient(transport=transport, base_url="https://score.test") as inner:
        client = ScoreEngineClient(base_url="https://score.test", api_key="fake")
        with pytest.raises(ScoreEngineError) as exc_info:
            await client.evaluate({}, client=inner)
        assert exc_info.value.status == 400


async def test_client_5xx_reintenta_y_levanta_si_persiste() -> None:
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, text="upstream down")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://score.test") as inner:
        client = ScoreEngineClient(base_url="https://score.test", api_key="fake")
        with pytest.raises(ScoreEngineError) as exc_info:
            await client.evaluate({}, client=inner)
        assert exc_info.value.status == 503
        # MAX_RETRIES=1 → 2 intentos totales
        assert calls["n"] == 2


# ─── ScoreReader (skip silencioso) ────────────────────────────────────────


async def test_reader_skip_silencioso_sin_uri() -> None:
    reader = ScoreReader(uri="", database="x")
    assert reader.enabled is False
    records = await reader.get_recent(workspace_id="RODDOS")
    assert records == []
    none = await reader.get_by_id("anything")
    assert none is None


# ─── Reader contra Mongo real (integration) ───────────────────────────────


pytestmark_integration = pytest.mark.skipif(
    not REAL_URI,
    reason="MONGODB_URI no disponible · integration tests saltados",
)


@pytest_asyncio.fixture
async def shared_db_with_seed() -> AsyncIterator[str]:
    """Usa el mismo cluster (REAL_URI) pero una DB simulando RODDOS-web."""
    db_name = os.environ.get("RODDOS_TEST_DATABASE", "argos_test_roddos_shared")
    client = AsyncIOMotorClient(REAL_URI, serverSelectionTimeoutMS=5000)
    db = client[db_name]
    await db["scoring_solicitudes"].drop()
    now = datetime.now(tz=UTC)
    await db["scoring_solicitudes"].insert_many([
        {
            "workspace_id": "RODDOS",
            "solicitud_id": "SCR-EXTERNAL-001",
            "producto": "credito_rodante",
            "monto_solicitado": 800_000,
            "score_final": 720,
            "decision": "aprobado",
            "narrativa": "from Iván engine",
            "engine_version": "ext_v1.0",
            "kyc": {"nombre": "Andrés San Juan"},
            "created_at": now,
        },
        {
            "workspace_id": "RODDOS",
            "solicitud_id": "SCR-EXTERNAL-002",
            "producto": "credito_rdx_leasing",
            "monto_solicitado": 5_000_000,
            "score_final": 540,
            "decision": "rechazado",
            "narrativa": "DTI alto",
            "engine_version": "ext_v1.0",
            "kyc": {"nombre": "Cliente Rechazado"},
            "created_at": now,
        },
        # Workspace ajeno · NO debe leerse (ROG-A3)
        {
            "workspace_id": "OTHER",
            "solicitud_id": "SCR-OTHER-001",
            "producto": "credito_rodante",
            "score_final": 800,
            "decision": "aprobado",
            "created_at": now,
        },
    ])
    try:
        yield db_name
    finally:
        await db["scoring_solicitudes"].drop()
        client.close()


@pytestmark_integration
async def test_reader_lee_solicitudes_filtradas_por_workspace(shared_db_with_seed: str) -> None:
    reader = ScoreReader(uri=REAL_URI, database=shared_db_with_seed)
    try:
        records = await reader.get_recent(workspace_id="RODDOS", limit=10)
    finally:
        await reader.close()
    assert len(records) == 2
    ids = {r.solicitud_id for r in records}
    assert ids == {"SCR-EXTERNAL-001", "SCR-EXTERNAL-002"}
    # ROG-A3: cross-workspace excluded
    assert "SCR-OTHER-001" not in ids


@pytestmark_integration
async def test_reader_get_by_id(shared_db_with_seed: str) -> None:
    reader = ScoreReader(uri=REAL_URI, database=shared_db_with_seed)
    try:
        rec = await reader.get_by_id("SCR-EXTERNAL-001")
    finally:
        await reader.close()
    assert rec is not None
    assert rec.score_final == 720
    assert rec.decision == "aprobado"
    assert rec.nombre == "Andrés San Juan"


# ─── API endpoints ────────────────────────────────────────────────────────


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
async def test_api_evaluate_pass_through_y_solicitudes_lee_shared_db(
    shared_db_with_seed: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /evaluate forwardea al Score Engine · GET /solicitudes lee el shared DB."""
    monkeypatch.setenv("RODDOS_MONGODB_URI", REAL_URI)
    monkeypatch.setenv("RODDOS_MONGODB_DATABASE", shared_db_with_seed)
    monkeypatch.setenv("SCORE_ENGINE_API_URL", "https://score-engine.test")
    monkeypatch.setenv("SCORE_ENGINE_API_KEY", "fake-key")

    headers = {"Authorization": f"Bearer {_ceo_token()}", "X-Workspace-Id": "RODDOS"}

    # Mock del Score Engine externo via monkey-patch del httpx.AsyncClient
    def mock_handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/v1/evaluate"
        assert req.headers.get("authorization") == "Bearer fake-key"
        return httpx.Response(
            200,
            json={
                "decision": "aprobado",
                "score_final": 700,
                "solicitud_id": "SCR-MOCK-1",
                "narrativa": "ok",
            },
        )

    # Inyecta un transport custom en httpx.AsyncClient via monkeypatch del constructor
    original_async_client = httpx.AsyncClient

    def patched(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        url = kwargs.get("base_url") or (args[0] if args else "")
        if "score-engine.test" in str(url):
            kwargs["transport"] = httpx.MockTransport(mock_handler)
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", patched)

    async for client in _authed_client(monkeypatch):
        resp = await client.post(
            "/api/v1/score/evaluate",
            headers=headers,
            json={"cedula": "80075452", "nombre": "Andrés"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["decision"] == "aprobado"
        assert body["score_final"] == 700

        resp_list = await client.get("/api/v1/score/solicitudes?limit=5", headers=headers)
        assert resp_list.status_code == 200
        items = resp_list.json()
        assert len(items) == 2  # los 2 RODDOS del shared DB
        assert all(s["decision"] in {"aprobado", "rechazado"} for s in items)
