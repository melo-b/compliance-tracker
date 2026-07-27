from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import date

# ==========================================
# 1. REGULATORY STANDARD SCHEMAS
# Represents the actual standards (e.g., UL, CSA, IEC)
# ==========================================

class StandardBase(BaseModel):
    name: str = Field(..., description="The standard designation (e.g., IEC 62368-1, UL 508)")
    agency: str = Field(..., description="The regulatory body or agency (e.g., CSA, UL, CE, FCC)")
    description: Optional[str] = Field(None, description="Brief description of the safety or compliance requirements")

class StandardCreate(StandardBase):
    pass

class StandardUpdate(BaseModel):
    name: Optional[str] = None
    agency: Optional[str] = None
    description: Optional[str] = None

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