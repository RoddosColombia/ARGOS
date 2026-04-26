"""API Scout · trigger manual + listado de watch queries."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from argos.agents.scout.queries_repo import list_all_queries
from argos.agents.scout.service import tick
from argos.auth.deps import require_role
from argos.auth.schemas import UserOut
from argos.db.mongo import get_database, get_mongo_client

router = APIRouter(prefix="/api/v1/scout", tags=["scout"])


def _ensure_mongo() -> None:
    if get_mongo_client() is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB no conectado · operación scout no disponible",
        )


@router.post("/trigger")
async def trigger_scout(
    _user: Annotated[UserOut, Depends(require_role("ceo", "sistema"))],
) -> dict:
    """Ejecuta un tick Scout ad-hoc · solo roles ceo/sistema.

    Lee watch queries de Mongo, clasifica con Haiku, persiste solo relevantes.
    El tick normal corre vía APScheduler cada 6 h en prod (24 h en dev).
    """
    _ensure_mongo()
    db = get_database()
    stats = await tick(db)
    return stats.as_dict()


@router.get("/watch-queries")
async def list_watch_queries(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
) -> list[dict[str, Any]]:
    """Lista todas las watch queries del workspace del usuario · rol ceo.

    Devuelve activas + inactivas para que el CEO pueda ver el estado completo
    desde el dashboard. La edición (toggle activa, ajustar prioridad, agregar
    nuevas) llega en builds posteriores con endpoints PATCH/POST/DELETE.
    """
    _ensure_mongo()
    db = get_database()
    queries = await list_all_queries(db, user.workspace_id)
    return [
        {
            "id": str(q["_id"]),
            "workspace_id": q["workspace_id"],
            "query": q["query"],
            "source": q.get("source", "all"),
            "activa": bool(q.get("activa", True)),
            "prioridad": int(q.get("prioridad", 1)),
            "created_at": q["created_at"].isoformat() if q.get("created_at") else None,
        }
        for q in queries
    ]
