from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from argos.auth.schemas import UserOut
from argos.auth.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=True)


async def get_current_user(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> UserOut:
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    token_workspace = payload.get("workspace_id")
    header_workspace = request.headers.get("X-Workspace-Id")
    if header_workspace and token_workspace and header_workspace != token_workspace:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace del header no coincide con el del token",
        )

    return UserOut(
        email=payload["sub"],
        role=payload["role"],
        workspace_id=token_workspace,
    )


def require_role(*allowed: str):
    async def _checker(user: Annotated[UserOut, Depends(get_current_user)]) -> UserOut:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Rol {user.role} no autorizado",
            )
        return user
    return _checker
