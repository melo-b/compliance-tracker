import enum

from sqlalchemy import Enum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserRole(enum.StrEnum):
    ADMIN = "admin"
    ENGINEER = "engineer"
    READ_ONLY = "read_only"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    hashed_password: Mapped[str]
    is_active: Mapped[bool | None] = mapped_column(default=True)
    # New accounts are read-only until an admin promotes them
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole),
        default=UserRole.READ_ONLY,
        server_default=UserRole.READ_ONLY.name,
    )
