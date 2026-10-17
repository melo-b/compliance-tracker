from datetime import UTC, datetime, timedelta

import jwt
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.user import User, UserRole
from tests.helpers import TEST_PASSWORD, bearer

REGISTER = "/api/v1/auth/register/"
LOGIN = "/api/v1/auth/login/"
ME = "/api/v1/users/me"


def register(client, email="alice@example.com", password=TEST_PASSWORD, **extra):
    return client.post(REGISTER, json={"email": email, "password": password, **extra})


def login(client, email="alice@example.com", password=TEST_PASSWORD):
    return client.post(LOGIN, data={"username": email, "password": password})


# --- registration ---


def test_register_creates_a_read_only_user_and_never_returns_the_password(client):
    response = register(client)
    body = response.json()

    assert response.status_code == 201
    assert body["email"] == "alice@example.com"
    assert body["role"] == "read_only"
    assert body["is_active"] is True
    assert "password" not in body and "hashed_password" not in body


def test_register_cannot_choose_a_role(client):
    response = register(client, role="ADMIN")

    assert response.status_code == 201
    assert response.json()["role"] == "read_only"


def test_register_stores_an_argon2_hash(client, db_session):
    register(client)
    user = db_session.query(User).one()

    assert user.hashed_password.startswith("$argon2id$")
    assert TEST_PASSWORD not in user.hashed_password


def test_register_rejects_short_and_overlong_passwords(client):
    assert register(client, password="short").status_code == 422
    assert register(client, password="x" * 129).status_code == 422


def test_register_rejects_invalid_email(client):
    assert register(client, email="not-an-email").status_code == 422


def test_register_rejects_duplicate_email_case_insensitively(client):
    assert register(client, email="alice@example.com").status_code == 201
    assert register(client, email="ALICE@Example.com").status_code == 409


# --- login ---


def test_login_returns_a_working_bearer_token(client):
    register(client)
    response = login(client)
    token = response.json()["access_token"]

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    me = client.get(ME, headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"


def test_login_email_is_case_insensitive(client):
    register(client, email="alice@example.com")
    assert login(client, email="Alice@EXAMPLE.com").status_code == 200


def test_wrong_password_and_unknown_email_give_the_same_response(client):
    register(client)
    wrong_password = login(client, password="not-the-right-password")
    unknown_email = login(client, email="nobody@example.com")

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_disabled_account_cannot_log_in(client, make_user):
    make_user(email="gone@example.com", is_active=False)

    response = login(client, email="gone@example.com")

    assert response.status_code == 403
    assert response.json()["detail"] == "Account is disabled"


def test_login_upgrades_a_legacy_bcrypt_hash_to_argon2(client, make_user, db_session):
    legacy_hash = BcryptHasher().hash(TEST_PASSWORD)
    user = make_user(email="legacy@example.com", hashed_password=legacy_hash)
    assert user.hashed_password.startswith("$2")

    assert login(client, email="legacy@example.com").status_code == 200

    db_session.refresh(user)
    assert user.hashed_password.startswith("$argon2id$")
    assert login(client, email="legacy@example.com").status_code == 200


# --- using tokens ---


def test_protected_route_without_a_token_is_401(client):
    assert client.get(ME).status_code == 401


def test_garbage_token_is_401(client):
    assert client.get(ME, headers={"Authorization": "Bearer not.a.jwt"}).status_code == 401


def test_expired_token_is_401(client, make_user):
    user = make_user()
    token = create_access_token(str(user.id), expires_delta=timedelta(seconds=-5))

    assert client.get(ME, headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_tampered_token_is_401(client, make_user):
    user = make_user()
    token = bearer(user)["Authorization"].split(" ")[1]
    header, payload, signature = token.split(".")
    tampered = ".".join([header, payload, signature[:-4] + "AAAA"])

    assert client.get(ME, headers={"Authorization": f"Bearer {tampered}"}).status_code == 401


def test_token_signed_with_a_different_key_is_401(client, make_user):
    user = make_user()
    claims = {"sub": str(user.id), "exp": datetime.now(UTC) + timedelta(minutes=5)}
    forged = jwt.encode(claims, "y" * 48, algorithm="HS256")

    assert client.get(ME, headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_token_without_expiry_is_401(client, make_user):
    user = make_user()
    forged = jwt.encode({"sub": str(user.id)}, get_settings().secret_key, algorithm="HS256")

    assert client.get(ME, headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_token_for_a_nonexistent_user_is_401(client):
    token = create_access_token("9999")
    assert client.get(ME, headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_token_with_a_non_numeric_subject_is_401(client):
    token = create_access_token("alice@example.com")
    assert client.get(ME, headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_deactivating_a_user_revokes_their_existing_token(client, make_user, db_session):
    user = make_user()
    headers = bearer(user)
    assert client.get(ME, headers=headers).status_code == 200

    user.is_active = False
    db_session.commit()

    assert client.get(ME, headers=headers).status_code == 401


def test_role_changes_apply_to_tokens_already_issued(client, make_user, db_session):
    engineer = make_user(UserRole.ENGINEER)
    headers = bearer(engineer)
    payload = {"model_number": "M-1", "name": "Thing"}
    assert client.post("/api/v1/products/", json=payload, headers=headers).status_code == 201

    engineer.role = UserRole.READ_ONLY
    db_session.commit()

    payload["model_number"] = "M-2"
    assert client.post("/api/v1/products/", json=payload, headers=headers).status_code == 403
