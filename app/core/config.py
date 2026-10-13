from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The development key that was committed to git history before it was moved to
# the environment. It is public, so it must never be accepted again.
_COMPROMISED_SECRET_KEYS = {"your-super-secret-development-key-keep-it-safe"}
_MIN_SECRET_KEY_LENGTH = 32


class Settings(BaseSettings):
    """Application settings, read from environment variables (and a local .env file)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Defaults match the docker-compose database mapped to host port 5433
    database_url: str = "postgresql://postgres:password123@localhost:5433/compliance_db"
    # Alembic should use a direct (non-pooled) connection when the app uses a pooler such as
    # Neon's. Falls back to database_url when unset.
    migration_database_url: str | None = None

    # Required: there is deliberately no default so a missing key fails at startup.
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    celery_broker_url: str = "redis://localhost:6379/0"

    @field_validator("secret_key")
    @classmethod
    def _validate_secret_key(cls, value: str) -> str:
        if value in _COMPROMISED_SECRET_KEYS:
            raise ValueError("SECRET_KEY is a publicly known value; generate a new one")
        if len(value) < _MIN_SECRET_KEY_LENGTH:
            raise ValueError(f"SECRET_KEY must be at least {_MIN_SECRET_KEY_LENGTH} characters")
        return value

    @property
    def alembic_database_url(self) -> str:
        return self.migration_database_url or self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
