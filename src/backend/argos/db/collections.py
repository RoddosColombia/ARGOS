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

# ─── Build 1.1 ───────────────────────────────────────────────────────────
WATCH_QUERIES = "watch_queries"

ALL_BUILD_1_1: tuple[str, ...] = (
    WATCH_QUERIES,
)

# ─── Build 1.3 ───────────────────────────────────────────────────────────
KEYWORDS = "keywords"

ALL_BUILD_1_3: tuple[str, ...] = (
    KEYWORDS,
)

# ─── Build 2.1 ───────────────────────────────────────────────────────────
ADS_LIBRARY = "ads_library"

ALL_BUILD_2_1: tuple[str, ...] = (
    ADS_LIBRARY,
)

# ─── Build 2.3 ───────────────────────────────────────────────────────────
SOCIAL_ACCOUNTS = "social_accounts"
SOCIAL_POSTS = "social_posts"

ALL_BUILD_2_3: tuple[str, ...] = (
    SOCIAL_ACCOUNTS,
    SOCIAL_POSTS,
)

# ─── Build 3.1 ───────────────────────────────────────────────────────────
BRIEFINGS = "briefings"

ALL_BUILD_3_1: tuple[str, ...] = (
    BRIEFINGS,
)

# ─── Build 3.3 ───────────────────────────────────────────────────────────
RECOMMENDATIONS = "recommendations"

ALL_BUILD_3_3: tuple[str, ...] = (
    RECOMMENDATIONS,
)

# ─── Build 4.1 ───────────────────────────────────────────────────────────
SISMO_INVENTORY = "sismo_inventory"

ALL_BUILD_4_1: tuple[str, ...] = (
    SISMO_INVENTORY,
)

# ─── Build 4.2 ───────────────────────────────────────────────────────────
SISMO_SALES_DAILY = "sismo_sales_daily"

ALL_BUILD_4_2: tuple[str, ...] = (
    SISMO_SALES_DAILY,
)

# ─── Build config-intelligence ───────────────────────────────────────────
CATEGORIES = "categories"
DISCOVERY_SUGGESTIONS = "discovery_suggestions"

ALL_BUILD_CONFIG: tuple[str, ...] = (
    CATEGORIES,
    DISCOVERY_SUGGESTIONS,
)

# Unión · útil para fixtures de teardown
ALL_KNOWN: tuple[str, ...] = (
    ALL_BUILD_0_3
    + ALL_BUILD_1_0
    + ALL_BUILD_1_1
    + ALL_BUILD_1_3
    + ALL_BUILD_2_1
    + ALL_BUILD_2_3
    + ALL_BUILD_3_1
    + ALL_BUILD_3_3
    + ALL_BUILD_4_1
    + ALL_BUILD_4_2
    + ALL_BUILD_CONFIG
)
