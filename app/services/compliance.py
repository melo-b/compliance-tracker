"""Compliance records: queries, filters, edits and workflow transitions.

Validity (Valid / Expiring Soon / Expired) is never stored, but people still need to filter and
count by it. `validity_clause` expresses the same rule as `compute_validity` in SQL, using
boundary dates calculated in Python, so the two can never disagree (a test checks every boundary
against both).
"""

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import ColumnElement, and_, case, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.exceptions import ConflictError, InvalidRequestError, NotFoundError
from app.models.product import Product
from app.models.standard import ProductCompliance, Standard, WorkflowStatus
from app.models.user import UserRole
from app.schemas.pagination import PageParams
from app.schemas.standard import ProductComplianceCreate, ProductComplianceUpdate
from app.services.compliance_logic import Validity, check_transition, utc_today
from app.services.querying import apply_sorting, contains, paginate

# Pending -> Draft -> Final, so sorting by workflow follows the workflow, on every database.
# (Written as comparisons so each value goes through the column's Enum type; passing the
# members as plain CASE values would compare the text "Pending" with the stored name PENDING.)
_WORKFLOW_ORDER = case(
    (ProductCompliance.workflow_status == WorkflowStatus.PENDING, 0),
    (ProductCompliance.workflow_status == WorkflowStatus.DRAFT, 1),
    else_=2,
)

SORTABLE = {
    "id": ProductCompliance.id,
    "expiration_date": ProductCompliance.expiration_date,
    "issued_date": ProductCompliance.issued_date,
    "workflow_status": _WORKFLOW_ORDER,
    "product_id": ProductCompliance.product_id,
    "standard_id": ProductCompliance.standard_id,
    "certificate_number": ProductCompliance.certificate_number,
    "agency": ProductCompliance.agency,
}

ALREADY_MAPPED = "Product is already mapped to this standard"


@dataclass(frozen=True)
class ComplianceFilters:
    workflow_status: WorkflowStatus | None = None
    validity: Validity | None = None
    product_id: int | None = None
    standard_id: int | None = None
    expiring_within_days: int | None = None
    q: str | None = None


def with_relations():
    """A select for compliance records that loads the product and standard in two extra queries
    (not one per row)."""
    return select(ProductCompliance).options(
        selectinload(ProductCompliance.product), selectinload(ProductCompliance.standard)
    )


def validity_clause(
    validity: Validity, today: date, window_days: int | None = None
) -> ColumnElement[bool]:
    """SQL condition for "this record is currently <validity>". Same rule as compute_validity."""
    window = get_settings().expiring_soon_days if window_days is None else window_days
    soon_limit = today + timedelta(days=window)
    final = ProductCompliance.workflow_status == WorkflowStatus.FINAL
    expires = ProductCompliance.expiration_date

    if validity == Validity.EXPIRED:
        return and_(final, expires < today)
    if validity == Validity.EXPIRING_SOON:
        return and_(final, expires >= today, expires <= soon_limit)
    return and_(final, or_(expires.is_(None), expires > soon_limit))


def _apply_filters(statement, filters: ComplianceFilters, today: date):
    if filters.workflow_status:
        statement = statement.where(ProductCompliance.workflow_status == filters.workflow_status)
    if filters.validity:
        statement = statement.where(validity_clause(filters.validity, today))
    if filters.product_id is not None:
        statement = statement.where(ProductCompliance.product_id == filters.product_id)
    if filters.standard_id is not None:
        statement = statement.where(ProductCompliance.standard_id == filters.standard_id)
    if filters.expiring_within_days is not None:
        # Final certificates that have not expired yet but will within N days
        statement = statement.where(
            ProductCompliance.workflow_status == WorkflowStatus.FINAL,
            ProductCompliance.expiration_date >= today,
            ProductCompliance.expiration_date
            <= today + timedelta(days=filters.expiring_within_days),
        )
    if filters.q:
        statement = statement.where(
            contains(ProductCompliance.certificate_number, filters.q)
            | contains(ProductCompliance.agency, filters.q)
        )
    return statement


def list_records(
    db: Session,
    filters: ComplianceFilters,
    page: PageParams,
    sort: str | None,
    today: date | None = None,
) -> tuple[list[ProductCompliance], int]:
    statement = _apply_filters(with_relations(), filters, today or utc_today())
    statement = apply_sorting(statement, sort, SORTABLE, default="id")
    return paginate(db, statement, page)


def get_record(db: Session, record_id: int) -> ProductCompliance:
    record = db.scalar(with_relations().where(ProductCompliance.id == record_id))
    if record is None:
        raise NotFoundError("Compliance record not found")
    return record


def create_record(db: Session, data: ProductComplianceCreate) -> ProductCompliance:
    if db.get(Product, data.product_id) is None:
        raise NotFoundError("Product not found")
    if db.get(Standard, data.standard_id) is None:
        raise NotFoundError("Standard not found")

    already_mapped = db.scalar(
        select(ProductCompliance.id).where(
            ProductCompliance.product_id == data.product_id,
            ProductCompliance.standard_id == data.standard_id,
        )
    )
    if already_mapped:
        raise ConflictError(ALREADY_MAPPED)

    record = ProductCompliance(**data.model_dump())
    db.add(record)
    try:
        db.commit()
    except IntegrityError:  # the unique constraint caught a concurrent duplicate
        db.rollback()
        raise ConflictError(ALREADY_MAPPED) from None
    return get_record(db, record.id)


def update_record(db: Session, record_id: int, data: ProductComplianceUpdate) -> ProductCompliance:
    record = get_record(db, record_id)
    changes = data.model_dump(exclude_unset=True)

    # The dates must stay in order once the change is merged into what is already stored
    issued = changes.get("issued_date", record.issued_date)
    expires = changes.get("expiration_date", record.expiration_date)
    if issued is not None and expires is not None and expires < issued:
        raise InvalidRequestError("expiration_date cannot be before issued_date")

    for key, value in changes.items():
        setattr(record, key, value)
    db.commit()
    return get_record(db, record_id)


def transition_record(
    db: Session, record_id: int, target: WorkflowStatus, role: UserRole
) -> ProductCompliance:
    record = get_record(db, record_id)
    check_transition(record.workflow_status, target, role)  # raises 409 / 403 errors
    record.workflow_status = target
    db.commit()
    return get_record(db, record_id)


def delete_record(db: Session, record_id: int) -> None:
    record = get_record(db, record_id)
    db.delete(record)
    db.commit()
