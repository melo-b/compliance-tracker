import enum

from sqlalchemy import Boolean, Column, Enum, Integer, String

from app.db.base import Base


class UserRole(enum.StrEnum):
    ADMIN = "admin"
    ENGINEER = "engineer"
    READ_ONLY = "read_only"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    # New accounts are read-only until an admin promotes them
    role = Column(
        Enum(UserRole),
        default=UserRole.READ_ONLY,
        server_default=UserRole.READ_ONLY.name,
        nullable=False,
    )
