from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, InvalidRequestError, NotFoundError
from app.core.security import DUMMY_PASSWORD_HASH, hash_password, verify_password
from app.models.user import User, UserRole
from app.schemas.pagination import PageParams
from app.schemas.user import UserAdminUpdate
from app.services.querying import apply_sorting, contains, paginate

SORTABLE = {
    "id": User.id,
    "email": User.email,
    "role": User.role,
    "is_active": User.is_active,
}


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


def list_users(
    db: Session,
    page: PageParams,
    sort: str | None,
    q: str | None,
    role: UserRole | None,
    is_active: bool | None,
) -> tuple[list[User], int]:
    statement = select(User)
    if q:
        statement = statement.where(contains(User.email, q))
    if role:
        statement = statement.where(User.role == role)
    if is_active is not None:
        statement = statement.where(User.is_active == is_active)
    statement = apply_sorting(statement, sort, SORTABLE, default="id")
    return paginate(db, statement, page)


def admin_update_user(
    db: Session, admin: User, user_id: int, update: UserAdminUpdate
) -> User:
    # Blocking self-edits means an admin cannot demote or disable themselves and lock
    # everyone out of administration.
    if user_id == admin.id:
        raise InvalidRequestError("Admins cannot change their own role or active status")

    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")

    # An explicit null is ignored: role and is_active can never be unset
    changes = {k: v for k, v in update.model_dump(exclude_unset=True).items() if v is not None}
    for key, value in changes.items():
        setattr(user, key, value)

    db.commit()
    db.refresh(user)
    return user


def register_user(db: Session, email: str, password: str) -> User:
    if get_user_by_email(db, email):
        raise ConflictError("Email already registered")
    return create_user(db, email=email, password=password)
