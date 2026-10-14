from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import DUMMY_PASSWORD_HASH, hash_password, verify_password
from app.models.user import User, UserRole


def get_user_by_email(db: Session, email: str) -> User | None:
    """Case-insensitive lookup, so Alice@x.com and alice@x.com are the same account."""
    return db.query(User).filter(func.lower(User.email) == email.lower()).first()


def create_user(
    db: Session, email: str, password: str, role: UserRole = UserRole.READ_ONLY
) -> User:
    user = User(email=email.lower(), hashed_password=hash_password(password), role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Returns the user when the credentials are valid, otherwise None.

    Always performs one password verification, even for unknown emails, so timing does not
    reveal which emails are registered. Upgrades outdated password hashes on success.
    """
    user = get_user_by_email(db, email)
    if user is None:
        verify_password(password, DUMMY_PASSWORD_HASH)
        return None

    is_valid, upgraded_hash = verify_password(password, user.hashed_password)
    if not is_valid:
        return None

    if upgraded_hash:
        user.hashed_password = upgraded_hash
        db.commit()
    return user
