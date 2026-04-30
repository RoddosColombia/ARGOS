"""RiskSeal partner · digital footprint antifraude · stub Phase 2.

Mantenido en ARGOS como stub para Phase 3 cuando WhatsApp Agent lo invoque
durante el flujo KYC. El Score Engine externo (repo de Iván) tiene su propia
integración con RiskSeal · ARGOS NO la usa para evaluar scores.
"""
from argos.partners.riskseal.client import RiskSealClient, RiskSealResult

__all__ = ["RiskSealClient", "RiskSealResult"]
