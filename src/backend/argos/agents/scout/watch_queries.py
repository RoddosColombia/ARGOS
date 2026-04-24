"""Queries semilla para el Scout · Build 1.0.

Lista estática. Build 1.1 mueve a colección Mongo `scout_watch_queries` para
permitir edición sin deploy + activación/desactivación por workspace.
"""
from __future__ import annotations

WATCH_QUERIES: tuple[str, ...] = (
    "aceite moto",
    "pastillas freno moto",
    "filtro aire moto",
    "bujía moto",
    "cadena 428H moto",
    "llanta Pulsar 200",
    "batería moto",
    "kit arrastre TVS Raider",
    "amortiguador trasero moto",
    "espejo retrovisor universal moto",
    "repuestos TVS Raider 125",
)
