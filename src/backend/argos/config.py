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

    cors_origins: str = Field(default="", alias="ARGOS_CORS_ORIGINS")

    disable_scheduler: bool = Field(default=False, alias="ARGOS_DISABLE_SCHEDULER")

    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    apify_api_token: str = Field(default="", alias="APIFY_API_TOKEN")
    serpapi_api_key: str = Field(default="", alias="SERPAPI_API_KEY")
    tikhub_api_key: str = Field(default="", alias="TIKHUB_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    voyage_api_key: str = Field(default="", alias="VOYAGE_API_KEY")
    qdrant_url: str = Field(default="", alias="QDRANT_URL")
    qdrant_api_key: str = Field(default="", alias="QDRANT_API_KEY")

    @property
    def cors_origin_list(self) -> list[str]:
        if not self.cors_origins:
            return []
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
