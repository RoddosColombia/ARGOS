"""RiskSealClient · stub Phase 2 · ARGOS solo lo usará en Phase 3 (WhatsApp KYC).

El Score Engine externo (repo Iván) tiene su propia integración. Este stub queda
disponible para que el WhatsApp Agent ofrezca preview de fraude durante el flujo
de cotización · sin afectar la decisión final que toma el motor externo.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("argos.partners.riskseal")


@dataclass
class RiskSealResult:
    fraud_flag: bool
    risk_score: float


class RiskSealClient:
    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key

    @property
    def enabled(self) -> bool:
        return bool(self._api_key)

    async def check(self, cedula: str, nombre: str) -> RiskSealResult:
        if not self.enabled:
            logger.warning("riskseal_skipped_no_key")
            return RiskSealResult(fraud_flag=False, risk_score=0.5)
        raise NotImplementedError("RiskSeal real integration · Phase 3 con WhatsApp Agent")
