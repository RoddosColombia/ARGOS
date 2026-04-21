from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from argos.config import get_settings


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(
    subject: str,
    role: str,
    workspace_id: str,
    extra_claims: dict[str, Any] | None = None,
    ttl_minutes: int | None = None,
) -> str:
    settings = get_settings()
    now = datetime.now(tz=UTC)
    ttl = ttl_minutes if ttl_minutes is not None else settings.jwt_access_token_ttl_minutes
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "workspace_id": workspace_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl)).timestamp()),
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
