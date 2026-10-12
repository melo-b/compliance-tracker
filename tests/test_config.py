import pytest
from pydantic import ValidationError

from app.core.config import Settings

VALID_KEY = "k" * 48


def make_settings(**overrides):
    # _env_file=None keeps a developer's local .env out of these tests
    return Settings(_env_file=None, **overrides)


def test_secret_key_is_required(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        make_settings()


def test_secret_key_rejects_short_values():
    with pytest.raises(ValidationError, match="at least 32"):
        make_settings(secret_key="too-short")


def test_secret_key_rejects_the_old_committed_value():
    with pytest.raises(ValidationError, match="publicly known"):
        make_settings(secret_key="your-super-secret-development-key-keep-it-safe")


def test_settings_read_from_environment(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", VALID_KEY)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db.example/app")
    settings = make_settings()
    assert settings.secret_key == VALID_KEY
    assert settings.database_url == "postgresql://u:p@db.example/app"
    assert settings.algorithm == "HS256"
    assert settings.access_token_expire_minutes == 30


def test_migration_url_falls_back_to_database_url():
    settings = make_settings(secret_key=VALID_KEY, database_url="postgresql://pooled/app")
    assert settings.alembic_database_url == "postgresql://pooled/app"


def test_migration_url_overrides_database_url_when_set():
    settings = make_settings(
        secret_key=VALID_KEY,
        database_url="postgresql://pooled/app",
        migration_database_url="postgresql://direct/app",
    )
    assert settings.alembic_database_url == "postgresql://direct/app"
