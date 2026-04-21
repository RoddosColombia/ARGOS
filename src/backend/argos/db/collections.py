"""Nombres canónicos de colecciones MongoDB · ver docs/canonicas/colecciones_mongo.md"""
from __future__ import annotations

WORKSPACES = "workspaces"
USERS = "users"
ARGOS_EVENTS = "argos_events"
AUDIT_LOG = "audit_log"
SYSTEM_HEALTH = "system_health"

ALL_BUILD_0_3: tuple[str, ...] = (
    WORKSPACES,
    USERS,
    ARGOS_EVENTS,
    AUDIT_LOG,
    SYSTEM_HEALTH,
)
