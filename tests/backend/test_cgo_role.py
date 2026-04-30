"""Tests del rol CGO nativo + approval routing por plano (Build 2.5.5).

Cubre:
- Role enum incluye 'cgo' como literal válido
- JWT issued con role='cgo' es válido (no rechazado por schema)
- require_role permite 'cgo' donde se declare
- Recommendations approve/reject valida role vs approval_required_role:
  * approval_required_role='ceo' + user.role='ceo' → 200
  * approval_required_role='ceo' + user.role='cgo' → 403
  * approval_required_role='cgo' + user.role='cgo' → 200
  * approval_required_role='cgo' + user.role='ceo' → 200 (CEO override)
  * approval_required_role=None → cualquiera ceo|cgo → 200
"""
from __future__ import annotations

from argos.auth.security import create_access_token, decode_access_token


def test_role_enum_includes_cgo() -> None:
    """El Literal Role debe aceptar 'cgo' (Build 2.5.5)."""
    from argos.auth.schemas import Role

    # Literal['ceo','cgo','analista','sistema','cliente'] — verificamos via __args__
    valid_roles = set(Role.__args__)  # type: ignore[attr-defined]
    assert "cgo" in valid_roles, "Build 2.5.5: 'cgo' debe ser role nativo"
    assert "ceo" in valid_roles
    assert "analista" in valid_roles
    assert "sistema" in valid_roles
    assert "cliente" in valid_roles


def test_jwt_with_cgo_role_is_decodable() -> None:
    """Un token issued con role='cgo' debe decodificar bien."""
    token = create_access_token(
        subject="ivan@roddos.com",
        role="cgo",
        workspace_id="RODDOS",
    )
    claims = decode_access_token(token)
    assert claims["sub"] == "ivan@roddos.com"
    assert claims["role"] == "cgo"
    assert claims["workspace_id"] == "RODDOS"


def test_can_approve_helper_logic() -> None:
    """ROG-G2 · _can_approve enruta correctamente."""
    from argos.api.v1.recommendations import _can_approve

    # approval_required_role None → cualquier role autorizado pasa
    assert _can_approve("ceo", None)[0] is True
    assert _can_approve("cgo", None)[0] is True
    assert _can_approve("ceo", "")[0] is True
    assert _can_approve("ceo", "none")[0] is True

    # approval_required_role='ceo' → solo CEO
    can, reason = _can_approve("ceo", "ceo")
    assert can is True
    can, reason = _can_approve("cgo", "ceo")
    assert can is False
    assert "CEO" in reason

    # approval_required_role='cgo' → CGO o CEO (override)
    can, reason = _can_approve("cgo", "cgo")
    assert can is True
    can, reason = _can_approve("ceo", "cgo")
    assert can is True  # CEO override permitido

    # approval_required_role desconocido → fail-safe
    can, reason = _can_approve("ceo", "rey-magos")
    assert can is False
    assert "desconocido" in reason


def test_brief_recipient_dataclass() -> None:
    """BriefRecipient hereda role + email."""
    from argos.services.brief_delivery import BriefRecipient

    r = BriefRecipient(email="ivan@roddos.com", role="cgo")
    assert r.email == "ivan@roddos.com"
    assert r.role == "cgo"


def test_brief_channel_enum_values() -> None:
    from argos.services.brief_delivery import BriefChannel

    assert BriefChannel.DASHBOARD == "dashboard"
    assert BriefChannel.WHATSAPP == "whatsapp"
    assert BriefChannel.EMAIL == "email"
    assert BriefChannel.LOG_ONLY == "log_only"


# ─── Sanity check: el config tiene los campos CGO_* ──────────────────────


def test_settings_exposes_cgo_fields() -> None:
    """Settings debe leer CGO_EMAIL, CGO_PASSWORD_HASH, CGO_WORKSPACE_ID."""
    from argos.config import get_settings

    s = get_settings()
    # Los atributos existen aunque estén vacíos (la clase los declara)
    assert hasattr(s, "cgo_email")
    assert hasattr(s, "cgo_password_hash")
    assert hasattr(s, "cgo_workspace_id")
    # Default workspace para CGO es RODDOS (mismo que CEO)
    assert s.cgo_workspace_id == "RODDOS" or s.cgo_workspace_id == s.admin_workspace_id
