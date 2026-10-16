from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.product import Product
from app.models.standard import ProductCompliance, Standard, WorkflowStatus
from app.schemas.dashboard import DashboardSummary, DashboardTotals
from app.services.compliance import validity_clause, with_relations
from app.services.compliance_logic import Validity, utc_today


def _count(db: Session, *conditions) -> int:
    return db.scalar(select(func.count()).select_from(ProductCompliance).where(*conditions)) or 0


def build_summary(db: Session, limit: int = 10, today: date | None = None) -> DashboardSummary:
    """Everything the dashboard needs, so the UI makes one request instead of many."""
    today = today or utc_today()
    window = get_settings().expiring_soon_days

    by_workflow = {
        status.value: _count(db, ProductCompliance.workflow_status == status)
        for status in WorkflowStatus
    }
    by_validity = {v.value: _count(db, validity_clause(v, today, window)) for v in Validity}

    expiring_soon = db.scalars(
        with_relations()
        .where(validity_clause(Validity.EXPIRING_SOON, today, window))
        .order_by(ProductCompliance.expiration_date.asc(), ProductCompliance.id.asc())
        .limit(limit)
    ).all()
    expired = db.scalars(
        with_relations()
        .where(validity_clause(Validity.EXPIRED, today, window))
        .order_by(ProductCompliance.expiration_date.desc(), ProductCompliance.id.asc())
        .limit(limit)
    ).all()

    return DashboardSummary(
        as_of=today,
        expiring_soon_days=window,
        totals=DashboardTotals(
            products=db.scalar(select(func.count()).select_from(Product)) or 0,
            standards=db.scalar(select(func.count()).select_from(Standard)) or 0,
            compliance_records=_count(db),
        ),
        by_workflow=by_workflow,
        by_validity=by_validity,
        expiring_soon=list(expiring_soon),
        expired=list(expired),
    )
