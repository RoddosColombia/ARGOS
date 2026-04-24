"""Detección de compatibilidad moto → SKU por regex sobre el título.

Build 1.0: heurística simple. Build 1.1 reemplaza con Haiku 4.5 para
categorización jerárquica real (`repuestos.frenos.pastillas`, etc.).
"""
from __future__ import annotations

import re

# Patterns ordenados por especificidad · el primero que matchea gana.
# Cada entrada es (nombre_moto_canónico, regex).
_MOTO_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("TVS Raider 125", re.compile(r"\b(tvs[\s-]?raider|raider[\s-]?125)\b", re.IGNORECASE)),
    ("Pulsar NS 200", re.compile(r"\b(pulsar[\s-]?ns[\s-]?200|ns[\s-]?200)\b", re.IGNORECASE)),
    ("Pulsar 200", re.compile(r"\b(pulsar[\s-]?200|pulsar200)\b", re.IGNORECASE)),
    ("Pulsar 180", re.compile(r"\b(pulsar[\s-]?180)\b", re.IGNORECASE)),
    ("Pulsar 150", re.compile(r"\b(pulsar[\s-]?150)\b", re.IGNORECASE)),
    ("Pulsar 135", re.compile(r"\b(pulsar[\s-]?135)\b", re.IGNORECASE)),
    ("Boxer CT 100", re.compile(r"\b(boxer[\s-]?ct[\s-]?100|boxer[\s-]?100)\b", re.IGNORECASE)),
    ("Discover 125", re.compile(r"\b(discover[\s-]?125)\b", re.IGNORECASE)),
    ("NKD 125", re.compile(r"\b(nkd[\s-]?125)\b", re.IGNORECASE)),
    ("CB 110", re.compile(r"\b(cb[\s-]?110)\b", re.IGNORECASE)),
    ("AKT 125", re.compile(r"\b(akt[\s-]?125|ak[\s-]?125)\b", re.IGNORECASE)),
]


def detect_compatible_motos(title: str) -> list[str]:
    """Retorna lista de modelos canónicos mencionados en el título. Puede estar vacía."""
    if not title:
        return []
    matches: list[str] = []
    for moto, pattern in _MOTO_PATTERNS:
        if pattern.search(title) and moto not in matches:
            matches.append(moto)
    return matches
