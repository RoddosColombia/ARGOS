"""RiskSealClient · Phase 2 stub · integración real llega en Phase 3.

Sin RISKSEAL_API_KEY → mock no-fraud · log warning. Permite que el ScoreEngine
corra end-to-end en dev sin gastar plata en partner real.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("argos.partners.riskseal")


@dataclass
class RiskSealResult:
    fraud_flag: bool
    risk_score: float  # 0.0 (alto riesgo) - 1.0 (bajo riesgo)


class RiskSealClient:
    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key

    @property
    def enabled(self) -> bool:
        return bool(self._api_key)

    async def check(self, cedula: str, nombre: str) -> RiskSealResult:
        if not self.enabled:
            logger.warning("riskseal_skipped_no_key", extra={"cedula_hash": hash(cedula) % 10000})
            return RiskSealResult(fraud_flag=False, risk_score=0.5)
        # Phase 3: implementar POST real a RiskSeal API
        raise NotImplementedError("RiskSeal real integration · Phase 3 con WhatsApp Agent")
