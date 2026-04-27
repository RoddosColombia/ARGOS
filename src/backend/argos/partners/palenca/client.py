"""PalencaClient · stub Phase 2 · ARGOS lo usará en Phase 3 (WhatsApp KYC)."""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("argos.partners.palenca")


@dataclass
class PalencaResult:
    ingreso_mensual: float
    estabilidad_meses: int


class PalencaClient:
    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key

    @property
    def enabled(self) -> bool:
        return bool(self._api_key)

    async def get_income(self, auth_code: str) -> PalencaResult:
        if not self.enabled:
            logger.warning("palenca_skipped_no_key")
            return PalencaResult(ingreso_mensual=2_500_000.0, estabilidad_meses=8)
        raise NotImplementedError("Palenca real integration · Phase 3")
