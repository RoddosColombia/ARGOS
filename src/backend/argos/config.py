from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Literal["dev", "staging", "prod"] = Field(default="dev", alias="ARGOS_ENV")
    log_level: str = Field(default="INFO", alias="ARGOS_LOG_LEVEL")
    version: str = Field(default="0.1.0", alias="ARGOS_VERSION")

    jwt_secret: str = Field(default="dev-secret-replace-me", alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_access_token_ttl_minutes: int = Field(default=60, alias="JWT_ACCESS_TOKEN_TTL_MINUTES")

    mongodb_uri: str = Field(default="", alias="MONGODB_URI")
    mongodb_database: str = Field(default="argos", alias="MONGODB_DATABASE")
    mongodb_test_database: str = Field(default="argos_test", alias="MONGODB_TEST_DATABASE")

    admin_email: str = Field(default="", alias="ADMIN_EMAIL")
    admin_password_hash: str = Field(default="", alias="ADMIN_PASSWORD_HASH")
    admin_role: str = Field(default="ceo", alias="ADMIN_ROLE")
    admin_workspace_id: str = Field(default="RODDOS", alias="ADMIN_WORKSPACE_ID")

    # Build 2.5.5 · CGO Iván Echeverri (ROG-G1). Mismo workspace que CEO.
    # Si las env vars están vacías, el seed del CGO se salta (no rompe boot).
    cgo_email: str = Field(default="", alias="CGO_EMAIL")
    cgo_password_hash: str = Field(default="", alias="CGO_PASSWORD_HASH")
    cgo_workspace_id: str = Field(default="RODDOS", alias="CGO_WORKSPACE_ID")

    # Default sano que incluye dominio público + dev local. Si Render NO propaga
    # ARGOS_CORS_ORIGINS, este fallback evita que el frontend rompa con CORS.
    # Override en Render con la lista exacta cuando se agreguen dominios.
    cors_origins: str = Field(
        default=(
            "http://localhost:5173,http://localhost:3000,"
            "https://argos.roddos.com"
        ),
        alias="ARGOS_CORS_ORIGINS",
    )

    disable_scheduler: bool = Field(default=False, alias="ARGOS_DISABLE_SCHEDULER")

    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    apify_api_token: str = Field(default="", alias="APIFY_API_TOKEN")
    serpapi_api_key: str = Field(default="", alias="SERPAPI_API_KEY")
    tikhub_api_key: str = Field(default="", alias="TIKHUB_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    voyage_api_key: str = Field(default="", alias="VOYAGE_API_KEY")
    qdrant_url: str = Field(default="", alias="QDRANT_URL")
    qdrant_api_key: str = Field(default="", alias="QDRANT_API_KEY")

    # SISMO V2 · Build 4.1 (read-only)
    sismo_api_url: str = Field(default="", alias="SISMO_API_URL")
    sismo_api_key: str = Field(default="", alias="SISMO_API_KEY")

    # Twilio WhatsApp · Build market-intelligence-complete
    twilio_account_sid: str = Field(default="", alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str = Field(default="", alias="TWILIO_AUTH_TOKEN")
    twilio_whatsapp_from: str = Field(default="", alias="TWILIO_WHATSAPP_FROM")
    twilio_whatsapp_to: str = Field(default="", alias="TWILIO_WHATSAPP_TO")

    # Mercately WhatsApp BSP · Build 3.1 (Capa 1)
    mercately_api_key: str = Field(default="", alias="MERCATELY_API_KEY")
    mercately_poll_interval_s: int = Field(default=30, alias="MERCATELY_POLL_INTERVAL_S")
    sismo_inbound_webhook_url: str = Field(default="", alias="SISMO_INBOUND_WEBHOOK_URL")
    mercately_webhook_secret: str = Field(default="", alias="MERCATELY_WEBHOOK_SECRET")
    whatsapp_reply_enabled: bool = Field(default=False, alias="ARGOS_WHATSAPP_REPLY_ENABLED")

    # Wava · pasarela Nequi/Daviplata · Build 3.3 (Capa 1)
    wava_merchant_key: str = Field(default="", alias="WAVA_MERCHANT_KEY")
    wava_api_url: str = Field(default="https://api.dev.wava.co/v1", alias="WAVA_API_URL")

    # Score Engine externo · repo de Iván · ARGOS solo lee resultados
    roddos_mongodb_uri: str = Field(default="", alias="RODDOS_MONGODB_URI")
    roddos_mongodb_database: str = Field(default="roddos_comercial", alias="RODDOS_MONGODB_DATABASE")
    score_engine_api_url: str = Field(default="", alias="SCORE_ENGINE_API_URL")
    score_engine_api_key: str = Field(default="", alias="SCORE_ENGINE_API_KEY")

    @property
    def cors_origin_list(self) -> list[str]:
        """Lista de orígenes permitidos, defensiva en profundidad.

        Combina el valor de ARGOS_CORS_ORIGINS (que puede venir de OS env, `.env`,
        o el default del Field) con un safety set que SIEMPRE incluye los hosts
        canónicos · evita romper producción si el env var llega vacío o stale.
        """
        # Siempre presentes: dominio público + dev local. ROG-A11 (aislamiento
        # de blast radius) no se viola: estos hosts son ARGOS, no SISMO.
        safety_net = {
            "http://localhost:5173",
            "http://localhost:3000",
            "https://argos.roddos.com",
        }
        from_env = {
            o.strip() for o in (self.cors_origins or "").split(",") if o.strip()
        }
        merged = sorted(safety_net | from_env)
        return merged


@lru_cache
def get_settings() -> Settings:
    return Settings()
