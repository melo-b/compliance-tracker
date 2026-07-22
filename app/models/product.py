from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.db.base import Base

class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    model_number = Column(String, unique=True, index=True, nullable=False)
    description = Column(String, nullable=True)

    # Relationships
    compliance_records = relationship("ProductCompliance", back_populates="product", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="product", cascade="all, delete-orphan")