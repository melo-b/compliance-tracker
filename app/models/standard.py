import enum
from sqlalchemy import Column, Integer, String, ForeignKey, Enum, Date
from sqlalchemy.orm import relationship
from app.db.base import Base


class StandardStatus(str, enum.Enum):
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
    
    id = Column(Integer, primary_key=True, index=True)
    standard_number = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    publication_date = Column(Date, nullable=True)
    effective_date = Column(Date, nullable=True)
    issuing_body = Column(String, nullable=False)
    status = Column(Enum(StandardStatus), default=StandardStatus.ACTIVE, nullable=False)

    # Relationships
    compliance_records = relationship("ProductCompliance", back_populates="standard", cascade="all, delete-orphan")

class ProductCompliance(Base):
    __tablename__ = "product_compliance"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    standard_id = Column(Integer, ForeignKey("standards.id"), nullable=False)
    
    workflow_status = Column(
        Enum(WorkflowStatus),
        default=WorkflowStatus.PENDING,
        server_default=WorkflowStatus.PENDING.name,
        nullable=False,
    )
    certificate_number = Column(String, nullable=True)
    issued_date = Column(Date, nullable=True)
    expiration_date = Column(Date, nullable=True)
    agency = Column(String, nullable=True)
    # Validity (Valid / Expiring Soon / Expired) is deliberately not stored: it is computed from
    # expiration_date and today's date (see app/services/compliance_logic.py), so it can never
    # be stale.

    # Relationships
    product = relationship("Product", back_populates="compliance_records")
    standard = relationship("Standard", back_populates="compliance_records")