"""Lista semilla de watch queries · usada SOLO por el seed inicial (Build 1.1+).

Build 1.0 leía esta lista directamente en `tick()`. Build 1.1+ las lee de la
colección Mongo `watch_queries`. La lista canónica de defaults vive ahora en
`argos/db/seed.py::_DEFAULT_WATCH_QUERIES` para mantener seed self-contained.

Mantenemos esta constante por retrocompatibilidad con tests del Build 1.0.
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
