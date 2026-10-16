from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_admin
from app.db.database import get_db
from app.models.user import User, UserRole
from app.schemas.pagination import Page, PageParams, make_page, pagination
from app.schemas.user import UserAdminUpdate, UserResponse
from app.services import users as user_service

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
@router.get("/", response_model=Page[UserResponse], dependencies=[Depends(require_admin)])
def list_users(
    page: PageParams = Depends(pagination),
    sort: str | None = Query(None, description="Comma-separated fields; prefix - for descending"),
    q: str | None = Query(None, description="Matches part of the email address"),
    role: UserRole | None = Query(None, description="Filter by role"),
    is_active: bool | None = Query(None, description="Filter active or disabled accounts"),
    db: Session = Depends(get_db),
):
    items, total = user_service.list_users(db, page, sort, q, role, is_active)
    return make_page(items, total, page)


# 3. Change another user's role or active flag (admin)
@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    update: UserAdminUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return user_service.admin_update_user(db, admin, user_id, update)
