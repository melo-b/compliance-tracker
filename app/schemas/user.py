from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128

# --- User Schemas ---

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str = Field(
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        description=f"At least {PASSWORD_MIN_LENGTH} characters",
    )

class UserResponse(UserBase):
    id: int
    is_active: bool
    role: UserRole

    model_config = ConfigDict(from_attributes=True)

class UserAdminUpdate(BaseModel):
    """Fields an admin may change on another user."""

    role: UserRole | None = None
    is_active: bool | None = None

# --- Token Schemas ---

class Token(BaseModel):
    access_token: str
    token_type: str
