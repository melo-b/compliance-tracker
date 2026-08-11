from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import date
from app.models.standard import StandardStatus

# ==========================================
# 1. REGULATORY STANDARD SCHEMAS
# Represents the actual standards (e.g., UL, CSA, IEC)
# ==========================================

class StandardBase(BaseModel):
    standard_number: str = Field(..., description="The official alphanumeric designation (e.g., UL 508, CSA C22.2 No. 14)")
    title: str = Field(..., description="The formal title of the regulatory standard")
    publication_date: Optional[date] = Field(None, description="Date the standard was published")
    effective_date: Optional[date] = Field(None, description="Date the standard goes into effect")
    issuing_body: str = Field(..., description="The organization issuing the standard (e.g., CSA, UL, CE)")
    status: StandardStatus = Field(default=StandardStatus.ACTIVE, description="Current lifecycle status of the standard")

class StandardCreate(StandardBase):
    pass

class StandardUpdate(BaseModel):
    standard_number: Optional[str] = None
    title: Optional[str] = None
    publication_date: Optional[date] = None
    effective_date: Optional[date] = None
    issuing_body: Optional[str] = None
    status: Optional[StandardStatus] = None

class StandardResponse(StandardBase):
    id: int
    
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 2. PRODUCT COMPLIANCE (ASSOCIATION) SCHEMAS
# Maps a specific component to a standard and tracks expiration
# ==========================================

class ProductComplianceBase(BaseModel):
    status: str = Field(..., description="Current certification status (e.g., Active, Pending, Expired, Revoked)")
    expiration_date: Optional[date] = Field(None, description="The exact date the certification expires, used by background workers")

class ProductComplianceCreate(ProductComplianceBase):
    product_id: int = Field(..., description="The ID of the manufactured product")
    standard_id: int = Field(..., description="The ID of the regulatory standard")

class ProductComplianceUpdate(BaseModel):
    status: Optional[str] = None
    expiration_date: Optional[date] = None

class ProductComplianceResponse(ProductComplianceBase):
    id: int
    product_id: int
    standard_id: int
    
    model_config = ConfigDict(from_attributes=True)