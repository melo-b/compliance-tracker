from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db 
from app.models.standard import Standard, ProductCompliance
from app.models.product import Product
from app.schemas.standard import (
    StandardResponse, 
    StandardCreate,
    StandardUpdate,
    ProductComplianceCreate,
    ProductComplianceUpdate,
    ProductComplianceResponse
)

router = APIRouter(prefix="/api/v1/standards", tags=["Standards"])

# 1. Create a Standard (POST)
@router.post("/", response_model=StandardResponse, status_code=201)
def create_standard(standard: StandardCreate, db: Session = Depends(get_db)):
    db_standard = db.query(Standard).filter(Standard.standard_number == standard.standard_number).first()
    if db_standard:
        raise HTTPException(status_code=400, detail="Standard number already registered")
        
    new_standard = Standard(**standard.model_dump())
    db.add(new_standard)
    db.commit()
    db.refresh(new_standard)
    return new_standard

# 2. Get All Standards (GET)
@router.get("/", response_model=List[StandardResponse])
def get_standards(db: Session = Depends(get_db), skip: int = 0, limit: int = 100):
    standards = db.query(Standard).offset(skip).limit(limit).all()
    return standards

# 3. Get a Specific Standard by ID (GET)
@router.get("/{standard_id}", response_model=StandardResponse)
def get_standard(standard_id: int, db: Session = Depends(get_db)):
    standard = db.query(Standard).filter(Standard.id == standard_id).first()
    
    if not standard:
        raise HTTPException(status_code=404, detail="Standard not found")
        
    return standard

# 4. Update a Standard (PATCH)
@router.patch("/{standard_id}", response_model=StandardResponse)
def update_standard(standard_id: int, standard_update: StandardUpdate, db: Session = Depends(get_db)):
    db_standard = db.query(Standard).filter(Standard.id == standard_id).first()
    
    if not db_standard:
        raise HTTPException(status_code=404, detail="Standard not found")
        
    update_data = standard_update.model_dump(exclude_unset=True)
    
    if "standard_number" in update_data:
        existing_standard = db.query(Standard).filter(Standard.standard_number == update_data["standard_number"]).first()
        if existing_standard and existing_standard.id != standard_id:
            raise HTTPException(status_code=400, detail="Standard number already registered to another entry")

    for key, value in update_data.items():
        setattr(db_standard, key, value)
        
    db.commit()
    db.refresh(db_standard)
    return db_standard

# 5. Delete a Standard (DELETE)
@router.delete("/{standard_id}", status_code=204)
def delete_standard(standard_id: int, db: Session = Depends(get_db)):
    db_standard = db.query(Standard).filter(Standard.id == standard_id).first()
    
    if not db_standard:
        raise HTTPException(status_code=404, detail="Standard not found")
        
    db.delete(db_standard)
    db.commit()
    return None




# ==========================================
# PRODUCT COMPLIANCE MAPPING ROUTES
# ==========================================

# 1. Create a Compliance Record (POST)
@router.post("/compliance/", response_model=ProductComplianceResponse, status_code=201)
def create_compliance_record(record: ProductComplianceCreate, db: Session = Depends(get_db)):
    # Verify the product exists
    product = db.query(Product).filter(Product.id == record.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
        
    # Verify the standard exists
    standard = db.query(Standard).filter(Standard.id == record.standard_id).first()
    if not standard:
        raise HTTPException(status_code=404, detail="Standard not found")
        
    # Check if this exact mapping already exists to prevent duplicates
    existing_mapping = db.query(ProductCompliance).filter(
        ProductCompliance.product_id == record.product_id,
        ProductCompliance.standard_id == record.standard_id
    ).first()
    
    if existing_mapping:
        raise HTTPException(status_code=400, detail="Product is already mapped to this standard")

    new_record = ProductCompliance(**record.model_dump())
    db.add(new_record)
    db.commit()
    db.refresh(new_record)
    return new_record

# 2. Get All Compliance Records (GET)
@router.get("/compliance/", response_model=List[ProductComplianceResponse])
def get_compliance_records(db: Session = Depends(get_db), skip: int = 0, limit: int = 100):
    records = db.query(ProductCompliance).offset(skip).limit(limit).all()
    return records

# 3. Get Compliance Records for a Specific Product (GET)
@router.get("/compliance/product/{product_id}", response_model=List[ProductComplianceResponse])
def get_product_compliance(product_id: int, db: Session = Depends(get_db)):
    records = db.query(ProductCompliance).filter(ProductCompliance.product_id == product_id).all()
    return records

# 4. Update a Compliance Record (PATCH)
@router.patch("/compliance/{record_id}", response_model=ProductComplianceResponse)
def update_compliance_record(record_id: int, record_update: ProductComplianceUpdate, db: Session = Depends(get_db)):
    db_record = db.query(ProductCompliance).filter(ProductCompliance.id == record_id).first()
    
    if not db_record:
        raise HTTPException(status_code=404, detail="Compliance record not found")
        
    update_data = record_update.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(db_record, key, value)
        
    db.commit()
    db.refresh(db_record)
    return db_record

# 5. Delete a Compliance Record (DELETE)
@router.delete("/compliance/{record_id}", status_code=204)
def delete_compliance_record(record_id: int, db: Session = Depends(get_db)):
    db_record = db.query(ProductCompliance).filter(ProductCompliance.id == record_id).first()
    
    if not db_record:
        raise HTTPException(status_code=404, detail="Compliance record not found")
        
    db.delete(db_record)
    db.commit()
    return None