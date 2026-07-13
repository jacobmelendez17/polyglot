"""Central settings. All secrets come from environment variables only."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    api_env: str = "development"
    database_url: str = "postgresql+psycopg://polyglot:polyglot_dev_only@localhost:5432/polyglot"
    redis_url: str = "redis://localhost:6379/0"
    api_cors_origins: str = "http://localhost:3000"

    # Auth (verified in slice 1c; declared now so config shape is stable)
    auth_jwks_url: str = ""
    auth_audience: str = "polyglot-api"
    auth_issuer: str = "polyglot-web"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
