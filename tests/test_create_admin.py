import pytest

from app.models.user import User, UserRole
from app.scripts import create_admin
from app.scripts.create_admin import ensure_admin
from tests.helpers import TEST_PASSWORD


def test_creates_a_new_admin(db_session):
    outcome = ensure_admin(db_session, "boss@example.com", TEST_PASSWORD)

    user = db_session.query(User).one()
    assert outcome == "created"
    assert user.role is UserRole.ADMIN
    assert user.is_active is True
    assert user.hashed_password.startswith("$argon2id$")


def test_promotes_an_existing_user_without_a_password(db_session, make_user):
    existing = make_user(UserRole.READ_ONLY, email="boss@example.com", is_active=False)

    outcome = ensure_admin(db_session, "BOSS@example.com", None)

    db_session.refresh(existing)
    assert outcome == "promoted"
    assert existing.role is UserRole.ADMIN
    assert existing.is_active is True
    assert db_session.query(User).count() == 1


def test_new_admin_needs_a_password(db_session):
    with pytest.raises(ValueError, match="password is required"):
        ensure_admin(db_session, "boss@example.com", None)


def test_new_admin_password_must_meet_the_policy(db_session):
    with pytest.raises(ValueError, match="characters long"):
        ensure_admin(db_session, "boss@example.com", "short")
    assert db_session.query(User).count() == 0


def test_cli_reads_the_password_from_the_environment(db_session, monkeypatch, capsys):
    monkeypatch.setattr(create_admin, "SessionLocal", lambda: db_session)
    monkeypatch.setenv("ADMIN_PASSWORD", TEST_PASSWORD)

    exit_code = create_admin.main(["--email", "cli@example.com"])

    assert exit_code == 0
    assert "Admin created: cli@example.com" in capsys.readouterr().out
    assert db_session.query(User).filter_by(email="cli@example.com").one().role is UserRole.ADMIN


def test_cli_reports_errors_without_a_traceback(db_session, monkeypatch, capsys):
    monkeypatch.setattr(create_admin, "SessionLocal", lambda: db_session)
    monkeypatch.setenv("ADMIN_PASSWORD", "short")

    exit_code = create_admin.main(["--email", "cli@example.com"])

    assert exit_code == 1
    assert "Error:" in capsys.readouterr().err
