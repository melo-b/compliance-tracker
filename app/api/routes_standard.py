from fastapi import APIRouter, Depends, HTTPException, Query
from kombu.exceptions import OperationalError as BrokerUnavailableError
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin, require_engineer, require_user
from app.db.database import get_db
from app.models.standard import StandardStatus, WorkflowStatus
from app.models.user import User
from app.schemas.pagination import Page, PageParams, make_page, pagination
from app.schemas.standard import (
    ProductComplianceCreate,
    ProductComplianceResponse,
    ProductComplianceUpdate,
    StandardCreate,
    StandardResponse,
    StandardUpdate,
    WorkflowTransition,
)
from app.services import compliance as compliance_service
from app.services import standards as standard_service
from app.services.compliance import ComplianceFilters
from app.services.compliance_logic import Validity
from app.worker.tasks import scan_expiring_compliance_records

# Every route requires a logged-in user; writes additionally require a role (see README).
router = APIRouter(
    prefix="/api/v1/standards",
    tags=["Standards"],
    dependencies=[Depends(require_user)],
)

SORT_HELP = "Comma-separated fields; prefix - for descending"


# ==========================================
# STANDARDS
# ==========================================
@router.post(
    "/", response_model=StandardResponse, status_code=201, dependencies=[Depends(require_admin)]
)
def create_standard(standard: StandardCreate, db: Session = Depends(get_db)):
    return standard_service.create_standard(db, standard)


@router.get("/", response_model=Page[StandardResponse])
def list_standards(
    page: PageParams = Depends(pagination),
    sort: str | None = Query(None, description=SORT_HELP),
    q: str | None = Query(None, description="Matches part of the number or title"),
    status: StandardStatus | None = Query(None, description="Filter by lifecycle status"),
    issuing_body: str | None = Query(None, description="Matches part of the issuing body"),
    db: Session = Depends(get_db),
):
    items, total = standard_service.list_standards(db, page, sort, q, status, issuing_body)
    return make_page(items, total, page)


# ==========================================
# PRODUCT COMPLIANCE (certification records)
# These routes are declared before /{standard_id} so "compliance" is never read as an id.
# ==========================================
@router.post(
    "/compliance/",
    response_model=ProductComplianceResponse,
    status_code=201,
    dependencies=[Depends(require_engineer)],
)
def create_compliance_record(record: ProductComplianceCreate, db: Session = Depends(get_db)):
    return compliance_service.create_record(db, record)


@router.get("/compliance/", response_model=Page[ProductComplianceResponse])
def list_compliance_records(
    page: PageParams = Depends(pagination),
    sort: str | None = Query(None, description=SORT_HELP),
    workflow_status: WorkflowStatus | None = Query(None, description="Pending, Draft or Final"),
    validity: Validity | None = Query(
        None, description="Valid, Expiring Soon or Expired (only Final records have one)"
    ),
    product_id: int | None = Query(None, description="Only records for this product"),
    standard_id: int | None = Query(None, description="Only records for this standard"),
    expiring_within_days: int | None = Query(
        None, ge=0, le=3650, description="Final certificates that expire within this many days"
    ),
    q: str | None = Query(None, description="Matches part of the certificate number or agency"),
    db: Session = Depends(get_db),
):
    filters = ComplianceFilters(
        workflow_status=workflow_status,
        validity=validity,
        product_id=product_id,
        standard_id=standard_id,
        expiring_within_days=expiring_within_days,
        q=q,
    )
    items, total = compliance_service.list_records(db, filters, page, sort)
    return make_page(items, total, page)


@router.get("/compliance/product/{product_id}", response_model=Page[ProductComplianceResponse])
def list_product_compliance(
    product_id: int,
    page: PageParams = Depends(pagination),
    sort: str | None = Query(None, description=SORT_HELP),
    db: Session = Depends(get_db),
):
    filters = ComplianceFilters(product_id=product_id)
    items, total = compliance_service.list_records(db, filters, page, sort)
    return make_page(items, total, page)


@router.patch(
    "/compliance/{record_id}",
    response_model=ProductComplianceResponse,
    dependencies=[Depends(require_engineer)],
)
def update_compliance_record(
    record_id: int, record_update: ProductComplianceUpdate, db: Session = Depends(get_db)
):
    return compliance_service.update_record(db, record_id, record_update)


# Pending -> Draft -> Final, one step at a time. Only admins may move a record backward.
@router.post("/compliance/{record_id}/transition", response_model=ProductComplianceResponse)
def transition_compliance_record(
    record_id: int,
    transition: WorkflowTransition,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_engineer),
):
    return compliance_service.transition_record(db, record_id, transition.target, current_user.role)


@router.delete("/compliance/{record_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_compliance_record(record_id: int, db: Session = Depends(get_db)):
    compliance_service.delete_record(db, record_id)


@router.post("/compliance/scan/", status_code=202, dependencies=[Depends(require_admin)])
def trigger_expiry_scan():
    # .delay() is the Celery command that sends the task to Redis. The API immediately returns
    # a 202 Accepted while the worker builds the report. The window defaults to the
    # EXPIRING_SOON_DAYS setting.
    try:
        task = scan_expiring_compliance_records.delay()
    except BrokerUnavailableError:
        # e.g. the hosted demo, where no Redis broker or worker is running
        raise HTTPException(
            status_code=503, detail="The background task queue is not available"
        ) from None

    return {
        "message": "Compliance expiry scan triggered in the background.",
        "task_id": task.id,
    }


# ==========================================
# STANDARDS by id
# ==========================================
@router.get("/{standard_id}", response_model=StandardResponse)
def get_standard(standard_id: int, db: Session = Depends(get_db)):
    return standard_service.get_standard(db, standard_id)


@router.patch(
    "/{standard_id}", response_model=StandardResponse, dependencies=[Depends(require_admin)]
)
def update_standard(
    standard_id: int, standard_update: StandardUpdate, db: Session = Depends(get_db)
):
    return standard_service.update_standard(db, standard_id, standard_update)


@router.delete("/{standard_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_standard(standard_id: int, db: Session = Depends(get_db)):
    standard_service.delete_standard(db, standard_id)
