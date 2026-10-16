from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.standard import ProductCompliance


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str]
    model_number: Mapped[str] = mapped_column(unique=True, index=True)
    description: Mapped[str | None]

    # Relationships
    compliance_records: Mapped[list["ProductCompliance"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
