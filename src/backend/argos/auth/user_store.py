from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from argos.auth.security import verify_password
from argos.config import get_settings


@dataclass
class AuthenticatedUser:
    email: str
    role: str
    workspace_id: str


class UserStore(Protocol):
    async def authenticate(self, email: str, password: str) -> AuthenticatedUser | None:
        ...


class EnvUserStore:
    """Bootstrap user store backed by env vars. Swapped for MongoUserStore in Build 0.3."""

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


_store: UserStore = EnvUserStore()


def get_user_store() -> UserStore:
    return _store


def set_user_store(store: UserStore) -> None:
    global _store
    _store = store
