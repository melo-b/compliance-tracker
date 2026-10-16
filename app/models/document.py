from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.standard import Standard


def _utc_now() -> datetime:
    # The column stores naive UTC timestamps (as it always has)
    return datetime.now(UTC).replace(tzinfo=None)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_product_id", "product_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    filename: Mapped[str]  # the sanitised original name, shown to users
    file_path: Mapped[str]  # the storage key (see app/services/storage.py)
    upload_date: Mapped[datetime | None] = mapped_column(default=_utc_now)
    content_type: Mapped[str | None]
    size_bytes: Mapped[int | None]

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    standard_id: Mapped[int | None] = mapped_column(ForeignKey("standards.id"))

    # Relationships
    product: Mapped["Product"] = relationship(back_populates="documents")
    standard: Mapped["Standard | None"] = relationship()
