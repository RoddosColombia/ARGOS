from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from argos.auth.deps import get_current_user
from argos.auth.schemas import LoginRequest, Role, TokenResponse, UserOut
from argos.auth.security import create_access_token
from argos.auth.user_store import UserStore, get_user_store
from argos.config import get_settings
from argos.db.mongo import get_database, get_mongo_client
from argos.services.audit import ActionResult, ActorType, audit_write

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    return request.client.host


def _audit_db():
    """Devuelve el DB para audit_write o None si Mongo no está configurado.

    `audit_write` skipea silenciosamente con db=None · permite que el endpoint
    siga sirviendo en entornos sin Mongo (tests con EnvUserStore).
    """
    if get_mongo_client() is None:
        return None
    return get_database()


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    store: Annotated[UserStore, Depends(get_user_store)],
    request: Request,
) -> TokenResponse:
    user = await store.authenticate(payload.email, payload.password)
    db = _audit_db()
    if user is None:
        # Audit del intento fallido (ROG-A12).
        # workspace_id desconocido en login fallido · usamos placeholder "_unknown"
        # para no perder la huella sin violar ROG-A3 (no es query, es write).
        await audit_write(
            db,
            workspace_id="_unknown",
            actor_type=ActorType.USER,
            actor_id=payload.email,
            action="auth.login.failed",
            result=ActionResult.FAILURE,
            metadata={"reason": "invalid_credentials"},
            ip_address=_client_ip(request),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        )
    settings = get_settings()
    token = create_access_token(
        subject=user.email,
        role=user.role,
        workspace_id=user.workspace_id,
    )
    role_value: Role = user.role  # type: ignore[assignment]

    # Audit del login exitoso (ROG-A12 · cumple ROG-G3 con actor_role).
    await audit_write(
        db,
        workspace_id=user.workspace_id,
        actor_type=ActorType.USER,
        actor_id=user.email,
        actor_role=user.role,
        action="auth.login.success",
        result=ActionResult.SUCCESS,
        ip_address=_client_ip(request),
    )

    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_access_token_ttl_minutes * 60,
        role=role_value,
        workspace_id=user.workspace_id,
    )


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[UserOut, Depends(get_current_user)]) -> UserOut:
    return user
