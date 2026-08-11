import enum
from sqlalchemy import Column, Integer, String, ForeignKey, Enum, Date
from sqlalchemy.orm import relationship
from app.db.base import Base


class StandardStatus(str, enum.Enum):
    ACTIVE = "Active"
    PENDING = "Pending"
    RETIRED = "Retired"

class ComplianceStatus(str,enum.Enum):
    PENDING = "Pending"
    VALID = "Valid"
    EXPIRING_SOON = "Expiring Soon"
    EXPIRED = "Expired"

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
    
    status = Column(Enum(ComplianceStatus), default=ComplianceStatus.PENDING, nullable=False)
    expiration_date = Column(Date, nullable=True)

    # Relationships
    product = relationship("Product", back_populates="compliance_records")
    standard = relationship("Standard", back_populates="compliance_records")