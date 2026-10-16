import enum
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.product import Product


class StandardStatus(enum.StrEnum):
    ACTIVE = "Active"
    PENDING = "Pending"
    RETIRED = "Retired"


class WorkflowStatus(enum.StrEnum):
    """Where a certification project stands. Moves forward one step at a time."""

    PENDING = "Pending"  # waiting on the agency
    DRAFT = "Draft"  # certificate drafted, not yet issued
    FINAL = "Final"  # certificate issued


class Standard(Base):
    __tablename__ = "standards"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    standard_number: Mapped[str] = mapped_column(unique=True, index=True)
    title: Mapped[str]
    publication_date: Mapped[date | None]
    effective_date: Mapped[date | None]
    issuing_body: Mapped[str]
    status: Mapped[StandardStatus] = mapped_column(
        Enum(StandardStatus), default=StandardStatus.ACTIVE
    )

    # Relationships
    compliance_records: Mapped[list["ProductCompliance"]] = relationship(
        back_populates="standard", cascade="all, delete-orphan"
    )


class ProductCompliance(Base):
    __tablename__ = "product_compliance"
    __table_args__ = (
        # A product is mapped to a standard at most once (enforced by the database, not just
        # by a check in the API, so concurrent requests cannot create duplicates)
        UniqueConstraint(
            "product_id", "standard_id", name="uq_product_compliance_product_standard"
        ),
        Index("ix_product_compliance_standard_id", "standard_id"),
        # Serves the dashboard and the validity / expiry filters
        Index("ix_product_compliance_workflow_expiry", "workflow_status", "expiration_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    standard_id: Mapped[int] = mapped_column(ForeignKey("standards.id"))

    workflow_status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus),
        default=WorkflowStatus.PENDING,
        server_default=WorkflowStatus.PENDING.name,
    )
    certificate_number: Mapped[str | None]
    issued_date: Mapped[date | None]
    expiration_date: Mapped[date | None]
    agency: Mapped[str | None]
    # Validity (Valid / Expiring Soon / Expired) is deliberately not stored: it is computed from
    # expiration_date and today's date (see app/services/compliance_logic.py), so it can never
    # be stale.

    # Relationships
    product: Mapped["Product"] = relationship(back_populates="compliance_records")
    standard: Mapped["Standard"] = relationship(back_populates="compliance_records")
