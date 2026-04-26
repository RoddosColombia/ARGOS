"""API social · GET /api/v1/social/accounts + /api/v1/social/posts."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from argos.auth.deps import require_role
from argos.auth.schemas import UserOut
from argos.db import collections as col
from argos.db.mongo import get_database, get_mongo_client

router = APIRouter(prefix="/api/v1/social", tags=["social"])

MAX_LIMIT = 200


def _ensure_mongo() -> None:
    if get_mongo_client() is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB no conectado",
        )


@router.get("/accounts")
async def list_accounts(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 20,
) -> list[dict[str, Any]]:
    """Top cuentas del workspace · ordenadas por relevancia_score desc · rol ceo."""
    _ensure_mongo()
    db = get_database()
    cursor = (
        db[col.SOCIAL_ACCOUNTS]
        .find({"workspace_id": user.workspace_id})
        .sort("relevancia_score", -1)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    return [
        {
            "id": str(d["_id"]),
            "plataforma": d.get("plataforma", ""),
            "username": d.get("username", ""),
            "seguidores": int(d.get("seguidores") or 0),
            "engagement_rate": float(d.get("engagement_rate") or 0),
            "descripcion": d.get("descripcion", ""),
            "url_perfil": d.get("url_perfil", ""),
            "relevancia_score": float(d.get("relevancia_score") or 0),
            "fuente_query": d.get("fuente_query", ""),
        }
        for d in docs
    ]


@router.get("/posts")
async def list_posts(
    user: Annotated[UserOut, Depends(require_role("ceo"))],
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 30,
) -> list[dict[str, Any]]:
    """Posts virales del workspace · ordenados por vistas desc · rol ceo."""
    _ensure_mongo()
    db = get_database()
    cursor = (
        db[col.SOCIAL_POSTS]
        .find({"workspace_id": user.workspace_id})
        .sort("vistas", -1)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    return [
        {
            "id": str(d["_id"]),
            "plataforma": d.get("plataforma", ""),
            "username": d.get("username", ""),
            "post_external_id": d.get("post_external_id", ""),
            "url_post": d.get("url_post", ""),
            "descripcion": d.get("descripcion", ""),
            "vistas": int(d.get("vistas") or 0),
            "likes": int(d.get("likes") or 0),
            "comentarios": int(d.get("comentarios") or 0),
            "hashtags": list(d.get("hashtags") or []),
            "fecha_publicacion": (
                d["fecha_publicacion"].isoformat() if d.get("fecha_publicacion") else None
            ),
        }
        for d in docs
    ]
