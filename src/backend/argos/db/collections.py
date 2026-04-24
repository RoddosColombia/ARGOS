"""Nombres canónicos de colecciones MongoDB · ver docs/canonicas/colecciones_mongo.md"""
from __future__ import annotations

# ─── Build 0.3 ───────────────────────────────────────────────────────────
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

# ─── Build 1.0 ───────────────────────────────────────────────────────────
PRODUCTS_CATALOG = "products_catalog"
PRODUCTS_HISTORY = "products_history"

ALL_BUILD_1_0: tuple[str, ...] = (
    PRODUCTS_CATALOG,
    PRODUCTS_HISTORY,
)

# Unión · útil para fixtures de teardown
ALL_KNOWN: tuple[str, ...] = ALL_BUILD_0_3 + ALL_BUILD_1_0
