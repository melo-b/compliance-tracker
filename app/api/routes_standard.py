from typing import List

from fastapi import APIRouter, Depends, HTTPException
from kombu.exceptions import OperationalError as BrokerUnavailableError
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin, require_engineer, require_user
from app.db.database import get_db
from app.models.product import Product
from app.models.standard import ProductCompliance, Standard
from app.models.user import User
from app.schemas.standard import (
    ProductComplianceCreate,
    ProductComplianceResponse,
    ProductComplianceUpdate,
    StandardCreate,
    StandardResponse,
    StandardUpdate,
    WorkflowTransition,
)
from app.services.compliance_logic import (
    InvalidTransitionError,
    TransitionNotPermittedError,
    check_transition,
)
from app.worker.tasks import scan_expiring_compliance_records

# Every route requires a logged-in user; writes additionally require a role (see README).
router = APIRouter(
    prefix="/api/v1/standards",
    tags=["Standards"],
    dependencies=[Depends(require_user)],
)

# 1. Create a Standard (POST)
@router.post(
    "/", response_model=StandardResponse, status_code=201, dependencies=[Depends(require_admin)]
)
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
@router.patch(
    "/{standard_id}", response_model=StandardResponse, dependencies=[Depends(require_admin)]
)
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
@router.delete("/{standard_id}", status_code=204, dependencies=[Depends(require_admin)])
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
@router.post(
    "/compliance/",
    response_model=ProductComplianceResponse,
    status_code=201,
    dependencies=[Depends(require_engineer)],
)
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
@router.patch(
    "/compliance/{record_id}",
    response_model=ProductComplianceResponse,
    dependencies=[Depends(require_engineer)],
)
def update_compliance_record(record_id: int, record_update: ProductComplianceUpdate, db: Session = Depends(get_db)):
    db_record = db.query(ProductCompliance).filter(ProductCompliance.id == record_id).first()
    
    if not db_record:
        raise HTTPException(status_code=404, detail="Compliance record not found")
        
    update_data = record_update.model_dump(exclude_unset=True)

    # The dates must stay in order once the change is merged into what is already stored
    issued = update_data.get("issued_date", db_record.issued_date)
    expires = update_data.get("expiration_date", db_record.expiration_date)
    if issued is not None and expires is not None and expires < issued:
        raise HTTPException(
            status_code=422, detail="expiration_date cannot be before issued_date"
        )

    for key, value in update_data.items():
        setattr(db_record, key, value)

    db.commit()
    db.refresh(db_record)
    return db_record

# 5. Move a Compliance Record Through the Workflow (POST)
# Pending -> Draft -> Final, one step at a time. Only admins may move a record backward.
@router.post("/compliance/{record_id}/transition", response_model=ProductComplianceResponse)
def transition_compliance_record(
    record_id: int,
    transition: WorkflowTransition,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_engineer),
):
    db_record = db.query(ProductCompliance).filter(ProductCompliance.id == record_id).first()

    if not db_record:
        raise HTTPException(status_code=404, detail="Compliance record not found")

    try:
        check_transition(db_record.workflow_status, transition.target, current_user.role)
    except TransitionNotPermittedError as error:
        raise HTTPException(status_code=403, detail=str(error)) from None
    except InvalidTransitionError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None

    db_record.workflow_status = transition.target
    db.commit()
    db.refresh(db_record)
    return db_record

# 6. Delete a Compliance Record (DELETE)
@router.delete(
    "/compliance/{record_id}", status_code=204, dependencies=[Depends(require_admin)]
)
def delete_compliance_record(record_id: int, db: Session = Depends(get_db)):
    db_record = db.query(ProductCompliance).filter(ProductCompliance.id == record_id).first()
    
    if not db_record:
        raise HTTPException(status_code=404, detail="Compliance record not found")
        
    db.delete(db_record)
    db.commit()
    return None

# 7. Manually Trigger the Expiry Report (POST)
@router.post("/compliance/scan/", status_code=202, dependencies=[Depends(require_admin)])
def trigger_expiry_scan():
    # .delay() is the Celery command that sends the task to Redis
    # The API immediately returns a 202 Accepted while the worker builds the report. The
    # window defaults to the EXPIRING_SOON_DAYS setting.
    try:
        task = scan_expiring_compliance_records.delay()
    except BrokerUnavailableError:
        # e.g. the hosted demo, where no Redis broker or worker is running
        raise HTTPException(
            status_code=503, detail="The background task queue is not available"
        ) from None

    return {
        "message": "Compliance expiry scan triggered in the background.",
        "task_id": task.id
    }