from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The development key that was committed to git history before it was moved to
# the environment. It is public, so it must never be accepted again.
_COMPROMISED_SECRET_KEYS = {"your-super-secret-development-key-keep-it-safe"}
_MIN_SECRET_KEY_LENGTH = 32


class Settings(BaseSettings):
    """Application settings, read from environment variables (and a local .env file)."""

    # hide_input_in_errors: a validation error must never print the rejected value, because
    # it is usually a password or a key
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

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

    # A final certificate expiring within this many days is reported as "Expiring Soon"
    expiring_soon_days: int = Field(default=90, ge=1, le=3650)

    # Uploaded documents. The local disk is wiped on every Render deploy (free tier), so treat
    # it as temporary there; see app/services/storage.py for the storage abstraction.
    upload_dir: str = "uploads"
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=100 * 1024 * 1024)

    @field_validator("database_url", "migration_database_url")
    @classmethod
    def _validate_database_url(cls, value: str | None) -> str | None:
        if value is None:
            return value
        # Hosting platforms often hand out "postgres://", which SQLAlchemy 2 does not accept
        if value.startswith("postgres://"):
            value = "postgresql://" + value[len("postgres://"):]
        if not value.startswith(("postgresql://", "postgresql+", "sqlite:")):
            # Deliberately does not echo the value: it normally contains the password
            raise ValueError(
                "must be a database URL starting with postgresql:// "
                "(check the value was copied in full, without quotes or a leading 'psql' command)"
            )
        return value

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
