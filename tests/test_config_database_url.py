"""Settings validation added in Phase 4: DATABASE_URL checks and upload limits."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

KEY = "k" * 48


def make_settings(**overrides):
    return Settings(_env_file=None, secret_key=KEY, **overrides)


def test_postgres_shorthand_is_converted_for_sqlalchemy():
    settings = make_settings(database_url="postgres://user:pw@host:5432/db")
    assert settings.database_url == "postgresql://user:pw@host:5432/db"


@pytest.mark.parametrize(
    "value",
    [
        "postgresql://user:pw@host/db",
        "postgresql+psycopg2://user:pw@host/db",
        "sqlite:///./local.db",
        "sqlite:///:memory:",
    ],
)
def test_valid_database_urls_are_accepted(value):
    assert make_settings(database_url=value).database_url == value


@pytest.mark.parametrize(
    "value",
    [
        "not a url",
        "psql 'postgresql://user:SECRETPW@host/db'",  # the whole psql command was copied
        "//user:SECRETPW@host/db",  # the scheme was cut off
        '"postgresql://user:SECRETPW@host/db"',  # quotes included
        "mysql://user:SECRETPW@host/db",
        "",
    ],
)
def test_malformed_database_urls_are_rejected_with_a_helpful_message(value):
    with pytest.raises(ValidationError) as error:
        make_settings(database_url=value)

    message = str(error.value)
    assert "postgresql://" in message  # tells the person what is expected
    assert "SECRETPW" not in message  # and never echoes the password back


def test_the_migration_url_is_validated_too():
    with pytest.raises(ValidationError):
        make_settings(migration_database_url="nonsense")
    assert make_settings(migration_database_url=None).migration_database_url is None


def test_invalid_secrets_are_never_echoed_in_errors():
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, secret_key="short-but-secret")

    assert "short-but-secret" not in str(error.value)


@pytest.mark.parametrize("value", [0, 512, 200 * 1024 * 1024])
def test_upload_limit_must_be_sensible(value):
    with pytest.raises(ValidationError):
        make_settings(max_upload_bytes=value)


def test_upload_defaults():
    settings = make_settings()
    assert settings.max_upload_bytes == 10 * 1024 * 1024
    assert settings.upload_dir == "uploads"
