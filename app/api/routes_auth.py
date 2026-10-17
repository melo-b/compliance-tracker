from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.database import get_db
from app.schemas.user import Token, UserCreate, UserResponse
from app.services.users import authenticate_user, register_user

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


# 1. Register a new user (always created as READ_ONLY; an admin can promote them)
@router.post("/register/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, db: Session = Depends(get_db)):
    return register_user(db, email=user.email, password=user.password)


# 2. Login to get an access token
@router.post("/login/", response_model=Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    # OAuth2 specifies sending 'username', but we use email, so we map it here
    user = authenticate_user(db, form_data.username, form_data.password)

    # Same message for an unknown email and a wrong password
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # The password was correct, so it is safe to say why the account cannot be used
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    return {"access_token": create_access_token(subject=str(user.id)), "token_type": "bearer"}
