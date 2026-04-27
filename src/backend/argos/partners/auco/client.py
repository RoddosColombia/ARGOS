"""AucoClient · stub Phase 2 · ARGOS lo usará en Phase 3 (WhatsApp KYC)."""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("argos.partners.auco")


@dataclass
class AucoResult:
    score: float
    match: bool


class AucoClient:
    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key

    @property
    def enabled(self) -> bool:
        return bool(self._api_key)

    async def verify(self, selfie_base64: str, doc_base64: str) -> AucoResult:
        if not self.enabled:
            logger.warning("auco_skipped_no_key")
            return AucoResult(score=85.0, match=True)
        raise NotImplementedError("AUCO real integration · Phase 3")
