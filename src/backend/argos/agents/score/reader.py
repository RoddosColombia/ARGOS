"""ScoreReader · lectura read-only de scoring_solicitudes en MongoDB compartido.

Conecta al cluster `RODDOS_MONGODB_URI` (admin web · roddos_comercial DB)
para leer resultados que escribió el Score Engine externo (repo de Iván).

ARGOS NO escribe en este cluster · ROG-A11 (aislamiento de credenciales):
la connection string debe tener scope read-only sobre `scoring_solicitudes`.

Skip silencioso si `RODDOS_MONGODB_URI` no configurado → métodos retornan
listas vacías o None · permite que ARGOS arranque sin el Score Engine
disponible.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient

from argos.config import get_settings

logger = logging.getLogger("argos.agents.score.reader")

SCORING_COLLECTION = "scoring_solicitudes"


@dataclass
class ScoreRecord:
    """Subset de campos de scoring_solicitudes para exponer al frontend."""
    solicitud_id: str
    producto: str
    score_final: int
    decision: str
    nombre: str
    monto_solicitado: float
    narrativa: str
    regla_dura_aplicada: str | None
    engine_version: str
    created_at: str | None
    raw: dict[str, Any]  # doc completo por si el frontend lo necesita


class ScoreReader:
    """Cliente lazy · abre conexión al cluster RODDOS solo cuando se llama."""

    def __init__(self, uri: str = "", database: str = "roddos_comercial") -> None:
        if not uri or not database:
            settings = get_settings()
            self._uri = uri or settings.roddos_mongodb_uri
            self._database = database if database != "roddos_comercial" else settings.roddos_mongodb_database
        else:
            self._uri = uri
            self._database = database
        self._client: AsyncIOMotorClient | None = None

    @property
    def enabled(self) -> bool:
        return bool(self._uri)

    def _get_client(self) -> AsyncIOMotorClient | None:
        if not self.enabled:
            return None
        if self._client is None:
            self._client = AsyncIOMotorClient(self._uri, serverSelectionTimeoutMS=5000)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    async def get_recent(
        self,
        workspace_id: str = "RODDOS",
        *,
        limit: int = 20,
        decision: str | None = None,
    ) -> list[ScoreRecord]:
        client = self._get_client()
        if client is None:
            logger.warning("score_reader_skipped_no_uri")
            return []
        coll = client[self._database][SCORING_COLLECTION]
        q: dict[str, Any] = {"workspace_id": workspace_id}
        if decision:
            q["decision"] = decision
        try:
            cursor = coll.find(q).sort("created_at", -1).limit(limit)
            docs = await cursor.to_list(length=limit)
        except Exception:  # noqa: BLE001
            logger.exception("score_reader_query_failed")
            return []
        return [_to_record(d) for d in docs]

    async def get_by_id(
        self,
        solicitud_id: str,
        *,
        workspace_id: str = "RODDOS",
    ) -> ScoreRecord | None:
        client = self._get_client()
        if client is None:
            return None
        coll = client[self._database][SCORING_COLLECTION]
        try:
            doc = await coll.find_one({"workspace_id": workspace_id, "solicitud_id": solicitud_id})
        except Exception:  # noqa: BLE001
            logger.exception("score_reader_get_by_id_failed")
            return None
        return _to_record(doc) if doc else None


def _to_record(doc: dict[str, Any]) -> ScoreRecord:
    raw = {k: v for k, v in doc.items() if k != "_id"}
    return ScoreRecord(
        solicitud_id=str(doc.get("solicitud_id", "")),
        producto=str(doc.get("producto", "")),
        score_final=int(doc.get("score_final") or 0),
        decision=str(doc.get("decision", "")),
        nombre=str(doc.get("nombre") or doc.get("kyc", {}).get("nombre", "")),
        monto_solicitado=float(doc.get("monto_solicitado") or 0),
        narrativa=str(doc.get("narrativa", "")),
        regla_dura_aplicada=doc.get("regla_dura_aplicada"),
        engine_version=str(doc.get("engine_version", "")),
        created_at=doc["created_at"].isoformat() if doc.get("created_at") else None,
        raw=raw,
    )
