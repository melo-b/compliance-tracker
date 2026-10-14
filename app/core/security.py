from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import get_settings

settings = get_settings()

# ==========================================
# PASSWORD HASHING
# ==========================================
# New hashes use Argon2id (the first hasher). Existing bcrypt hashes still verify, and
# verify_password() reports a replacement hash so they are upgraded at the next login.
password_hash = PasswordHash((Argon2Hasher(), BcryptHasher()))

# Verified against when a login names an unknown email, so response time does not reveal
# whether the account exists.
DUMMY_PASSWORD_HASH = password_hash.hash("not-a-real-password")


def hash_password(password: str) -> str:
    """Converts a plain text password into a salted Argon2id hash."""
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> tuple[bool, str | None]:
    """Checks a password against a stored hash.

    Returns (is_valid, upgraded_hash). upgraded_hash is a replacement to store when the
    stored hash uses an outdated algorithm or settings, otherwise None.
    """
    try:
        return password_hash.verify_and_update(plain_password, hashed_password)
    except UnknownHashError:
        return False, None


# ==========================================
# JWT
# ==========================================
def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Creates a signed JWT identifying the user (by id) with an expiry."""
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {"sub": subject, "exp": expire, "iat": datetime.now(UTC)}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict:
    """Verifies the signature and expiry and returns the claims.

    Raises jwt.InvalidTokenError (including ExpiredSignatureError) for any bad token. The
    algorithm is pinned and exp/sub are mandatory, so unsigned or incomplete tokens fail.
    """
    return jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.algorithm],
        options={"require": ["exp", "sub"]},
    )
