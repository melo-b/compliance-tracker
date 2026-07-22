from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.db.base import Base

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)              
    file_path = Column(String, nullable=False)             
    upload_date = Column(DateTime, default=datetime.utcnow)
    
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    standard_id = Column(Integer, ForeignKey("standards.id"), nullable=True) 

    # Relationships
    product = relationship("Product", back_populates="documents")
    standard = relationship("Standard")