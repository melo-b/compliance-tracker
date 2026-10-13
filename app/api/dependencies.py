import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.database import get_db
from app.models.user import User, UserRole

# This points FastAPI's security tools to your login endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login/")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """
    Dependency that intercepts the request, verifies the JWT, and returns the active user.

    The role is read from the database on every request, so a role change or deactivation
    takes effect immediately instead of when the token expires.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, ValueError):
        raise credentials_exception from None

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_exception

    return user


def require_roles(*allowed_roles: UserRole):
    """Builds a dependency that allows only users holding one of the given roles."""

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return role_checker


# Permission levels used by the routers (see the role matrix in the README)
require_user = get_current_user  # any authenticated, active user (read access)
require_engineer = require_roles(UserRole.ADMIN, UserRole.ENGINEER)  # create and edit
require_admin = require_roles(UserRole.ADMIN)  # delete, standards, user management
