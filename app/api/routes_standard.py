from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db 
from app.models.standard import Standard
from app.schemas.standard import StandardResponse, StandardCreate, StandardUpdate

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