from datetime import UTC, datetime, timedelta

import jwt
import pytest
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

SETTINGS = get_settings()


def forge(claims: dict, key: str = SETTINGS.secret_key, algorithm: str = "HS256") -> str:
    return jwt.encode(claims, key, algorithm=algorithm)


def future(minutes: int = 5) -> datetime:
    return datetime.now(UTC) + timedelta(minutes=minutes)


# --- passwords ---

def test_new_hashes_use_argon2id():
    assert hash_password("a-long-enough-password").startswith("$argon2id$")


def test_correct_password_verifies_and_needs_no_upgrade():
    hashed = hash_password("a-long-enough-password")
    assert verify_password("a-long-enough-password", hashed) == (True, None)


def test_wrong_password_fails():
    hashed = hash_password("a-long-enough-password")
    assert verify_password("another-password-entirely", hashed) == (False, None)


def test_legacy_bcrypt_hash_verifies_and_returns_an_argon2_upgrade():
    legacy = BcryptHasher().hash("legacy-password-123")
    assert legacy.startswith("$2")

    is_valid, upgraded = verify_password("legacy-password-123", legacy)

    assert is_valid is True
    assert upgraded is not None and upgraded.startswith("$argon2id$")
    assert verify_password("legacy-password-123", upgraded) == (True, None)


def test_unrecognised_hash_is_a_failed_login_not_a_crash():
    assert verify_password("whatever-password", "not-a-real-hash") == (False, None)


# --- tokens ---

def test_token_round_trip():
    claims = decode_access_token(create_access_token(subject="42"))
    assert claims["sub"] == "42"
    assert "exp" in claims


def test_expired_token_is_rejected():
    token = create_access_token(subject="1", expires_delta=timedelta(seconds=-5))
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_token_signed_with_another_key_is_rejected():
    token = forge({"sub": "1", "exp": future()}, key="x" * 48)
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(token)


def test_unsigned_alg_none_token_is_rejected():
    token = jwt.encode({"sub": "1", "exp": future()}, key=None, algorithm="none")
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token)


def test_token_without_expiry_is_rejected():
    with pytest.raises(jwt.MissingRequiredClaimError):
        decode_access_token(forge({"sub": "1"}))


def test_token_without_subject_is_rejected():
    with pytest.raises(jwt.MissingRequiredClaimError):
        decode_access_token(forge({"exp": future()}))
