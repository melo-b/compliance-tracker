import enum
from sqlalchemy import Column, Integer, String, ForeignKey, Enum, Date
from sqlalchemy.orm import relationship
from app.db.base import Base

class ComplianceStatus(enum.Enum):
    PENDING = "Pending"
    VALID = "Valid"
    EXPIRING_SOON = "Expiring Soon"
    EXPIRED = "Expired"

class Standard(Base):
    __tablename__ = "standards"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)  
    agency = Column(String, nullable=False)                         
    description = Column(String, nullable=True)

    # Relationships
    compliance_records = relationship("ProductCompliance", back_populates="standard")

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