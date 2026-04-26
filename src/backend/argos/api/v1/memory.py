"""API memory · GET /api/v1/memory/search?q=&type=&limit=."""
from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from argos.agents.memory.service import _build_default_agent
from argos.auth.deps import require_role
from argos.auth.schemas import UserOut
from argos.db.mongo import get_mongo_client

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])

MAX_LIMIT = 50


@router.get("/search")
async def memory_search(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
    q: Annotated[str, Query(min_length=1, description="Texto de búsqueda")],
    type: Annotated[Literal["products", "ads"], Query(description="Colección")] = "products",
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 10,
) -> list[dict[str, Any]]:
    """Búsqueda semántica vector · rol ceo · scope al workspace del usuario.

    Si Qdrant o OpenAI no están configurados → devuelve `[]` con log warning
    (NO 500) · permite que el frontend renderice empty state amigable.
    """
    if get_mongo_client() is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB no conectado",
        )
    agent = _build_default_agent()
    if agent is None:
        return []

    try:
        if type == "products":
            hits = await agent.search_similar_products(q, limit=limit, workspace_id=user.workspace_id)
        else:
            hits = await agent.search_similar_ads(q, limit=limit, workspace_id=user.workspace_id)
    finally:
        await agent._qdrant.close()

    return [h.as_dict() for h in hits]
