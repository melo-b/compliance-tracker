from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_admin
from app.db.database import get_db
from app.models.user import User
from app.schemas.user import UserAdminUpdate, UserResponse

router = APIRouter(
    prefix="/api/v1/users",
    tags=["Users"],
    dependencies=[Depends(get_current_user)],
)


# 1. The logged-in user's own profile (any role)
@router.get("/me", response_model=UserResponse)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


# 2. List all users (admin)
@router.get("/", response_model=list[UserResponse], dependencies=[Depends(require_admin)])
def list_users(db: Session = Depends(get_db), skip: int = 0, limit: int = 100):
    return db.query(User).order_by(User.id).offset(skip).limit(limit).all()


# 3. Change another user's role or active flag (admin)
@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    update: UserAdminUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    # Blocking self-edits means an admin cannot demote or disable themselves and lock
    # everyone out of administration.
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admins cannot change their own role or active status",
        )

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # An explicit null is ignored: role and is_active can never be unset
    changes = {k: v for k, v in update.model_dump(exclude_unset=True).items() if v is not None}
    for key, value in changes.items():
        setattr(user, key, value)

    db.commit()
    db.refresh(user)
    return user
