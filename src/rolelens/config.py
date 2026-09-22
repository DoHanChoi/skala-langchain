"""Environment-backed application settings."""

from __future__ import annotations

from datetime import date
from functools import lru_cache

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """RoleLens runtime settings.

    Local connection strings are demonstrative defaults for Docker Compose.
    Production credentials must be supplied through the environment.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    model_provider: str = "openai"
    model_id: str = "gpt-4o-mini"
    model_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("MODEL_API_KEY", "OPENAI_API_KEY"),
    )

    database_admin_url: SecretStr = SecretStr(
        "postgresql+psycopg://rolelens_owner:rolelens_local_owner@127.0.0.1:55432/rolelens"
    )
    database_readonly_url: SecretStr = SecretStr(
        "postgresql+psycopg://rolelens_agent_ro:rolelens_local_readonly@127.0.0.1:55432/rolelens"
    )

    random_seed: int = 42
    data_as_of: date = date(2026, 9, 15)
    sql_statement_timeout_ms: int = Field(default=10_000, ge=100, le=60_000)
    max_query_rows: int = Field(default=100, ge=1, le=1_000)
    log_level: str = "INFO"

    @field_validator("model_provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized != "openai":
            raise ValueError("MVP currently supports MODEL_PROVIDER=openai only")
        return normalized

    def admin_url(self) -> str:
        return self.database_admin_url.get_secret_value()

    def readonly_url(self) -> str:
        return self.database_readonly_url.get_secret_value()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings for application entry points."""

    return Settings()
