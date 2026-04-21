from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field

Role = Literal["ceo", "analista", "sistema", "cliente"]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    role: Role
    workspace_id: str


class UserOut(BaseModel):
    email: EmailStr
    role: Role
    workspace_id: str
