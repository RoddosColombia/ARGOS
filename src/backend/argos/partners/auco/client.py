"""AucoClient · Phase 2 stub · integración real llega en Phase 3.

Sin AUCO_API_KEY → mock match con score=85.0. Phase 3 conecta a la API
biométrica real (cara vs cédula).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("argos.partners.auco")


@dataclass
class AucoResult:
    score: float  # 0-100 · ROG-S3 rechaza si <70
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
