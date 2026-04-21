from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.auth.security import verify_password
from argos.config import get_settings
from argos.db import collections as col

logger = logging.getLogger("argos.auth.user_store")


@dataclass
class AuthenticatedUser:
    email: str
    role: str
    workspace_id: str


class UserStore(Protocol):
    async def authenticate(self, email: str, password: str) -> AuthenticatedUser | None:
        ...


class EnvUserStore:
    """Fallback user store backed by env vars (usado cuando Mongo no está conectado)."""

    async def authenticate(self, email: str, password: str) -> AuthenticatedUser | None:
        settings = get_settings()
        if not settings.admin_email or not settings.admin_password_hash:
            return None
        if email.lower() != settings.admin_email.lower():
            return None
        if not verify_password(password, settings.admin_password_hash):
            return None
        return AuthenticatedUser(
            email=settings.admin_email,
            role=settings.admin_role,
            workspace_id=settings.admin_workspace_id,
        )


class MongoUserStore:
    """User store persistente sobre la colección `users`.

    Regla de rol: el JWT lleva un único `role` (string). Este store toma el PRIMER
    rol del array `roles` en Mongo. Si se necesita RBAC con múltiples roles activos
    simultáneos, escalar al CEO (ver canónica colecciones_mongo.md · nota en users).
    """

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._db = db

    async def authenticate(self, email: str, password: str) -> AuthenticatedUser | None:
        email_n = email.lower()
        doc = await self._db[col.USERS].find_one({"email": email_n})
        if doc is None:
            return None
        if not verify_password(password, doc.get("password_hash", "")):
            return None
        roles = doc.get("roles") or []
        if not roles:
            logger.warning("user_without_roles", extra={"email": email_n})
            return None
        return AuthenticatedUser(
            email=doc["email"],
            role=roles[0],
            workspace_id=doc["workspace_id"],
        )


_store: UserStore = EnvUserStore()


def get_user_store() -> UserStore:
    return _store


def set_user_store(store: UserStore) -> None:
    global _store
    _store = store
