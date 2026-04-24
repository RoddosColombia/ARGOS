"""API · POST /api/v1/scout/trigger · disparo manual del tick Scout."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from argos.agents.scout.service import tick
from argos.auth.deps import require_role
from argos.auth.schemas import UserOut
from argos.db.mongo import get_database, get_mongo_client

router = APIRouter(prefix="/api/v1/scout", tags=["scout"])


@router.post("/trigger")
async def trigger_scout(
    _user: Annotated[UserOut, Depends(require_role("ceo", "sistema"))],
) -> dict:
    """Ejecuta un tick Scout ad-hoc · solo roles ceo/sistema.

    Para uso manual del CEO desde dashboard o pruebas. El tick normal corre vía
    APScheduler cada 6 h en prod (24 h en dev).
    """
    if get_mongo_client() is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB no conectado · no se puede ejecutar scout tick",
        )
    db = get_database()
    stats = await tick(db)
    return stats.as_dict()
