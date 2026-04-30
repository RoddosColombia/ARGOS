from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field

# Build 2.5.5: `cgo` agregado como rol nativo (Iván Echeverri · ROG-G1).
# CGO recibe la misma información que CEO (brief unificado · ROG-G1) pero su
# scope de approval es Plano 2 (campañas, creative, audiencias, pricing táctico).
# CEO mantiene Plano 3 (estructura, partners, sourcing, margen piso).
Role = Literal["ceo", "cgo", "analista", "sistema", "cliente"]


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
