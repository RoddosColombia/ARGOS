from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from argos.auth.deps import get_current_user
from argos.auth.schemas import LoginRequest, Role, TokenResponse, UserOut
from argos.auth.security import create_access_token
from argos.auth.user_store import UserStore, get_user_store
from argos.config import get_settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    store: Annotated[UserStore, Depends(get_user_store)],
) -> TokenResponse:
    user = await store.authenticate(payload.email, payload.password)
    if user is None:
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
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_access_token_ttl_minutes * 60,
        role=role_value,
        workspace_id=user.workspace_id,
    )


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[UserOut, Depends(get_current_user)]) -> UserOut:
    return user
