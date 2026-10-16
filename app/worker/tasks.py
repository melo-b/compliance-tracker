from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.database import SessionLocal
from app.models.standard import ProductCompliance, WorkflowStatus
from app.services.compliance_logic import Validity, compute_validity, days_until_expiry, utc_today
from app.worker.celery_app import celery_app


def _describe(record: ProductCompliance, today: date) -> dict:
    """JSON-serialisable summary of a record for the report."""
    expires = record.expiration_date
    if expires is None:  # the scan only selects records that have an expiration date
        raise ValueError(f"Compliance record {record.id} has no expiration date")
    return {
        "id": record.id,
        "product_id": record.product_id,
        "standard_id": record.standard_id,
        "certificate_number": record.certificate_number,
        "expiration_date": expires.isoformat(),
        "days_until_expiry": days_until_expiry(record.expiration_date, today),
    }


@celery_app.task(name="scan_expiring_compliance_records")
def scan_expiring_compliance_records(days_threshold: int | None = None):
    """
    Builds a report of final certificates that have expired or expire within the window.

    The task only reads: validity is computed from the expiration date whenever a record is
    read, so there is no stored status to keep up to date. The report is the hook for
    notifications (e.g. an email digest). `days_threshold` defaults to EXPIRING_SOON_DAYS.
    """
    window = get_settings().expiring_soon_days if days_threshold is None else days_threshold

    # Create an independent database session for the background worker
    db: Session = SessionLocal()

    try:
        today = utc_today()

        # Only final certificates with an expiry date inside (or before) the window can matter
        candidates = (
            db.query(ProductCompliance)
            .filter(
                ProductCompliance.workflow_status == WorkflowStatus.FINAL,
                ProductCompliance.expiration_date.isnot(None),
                ProductCompliance.expiration_date <= today + timedelta(days=window),
            )
            .order_by(ProductCompliance.expiration_date, ProductCompliance.id)
            .all()
        )

        # The same function the API uses, so the report can never disagree with it
        expiring_soon, expired = [], []
        for record in candidates:
            validity = compute_validity(
                record.workflow_status, record.expiration_date, today, window
            )
            # The query only returns final records expiring within the window or already past
            # it, so each one is in exactly one of the two groups
            assert validity in (Validity.EXPIRED, Validity.EXPIRING_SOON)
            if validity == Validity.EXPIRED:
                expired.append(_describe(record, today))
            else:
                expiring_soon.append(_describe(record, today))

        return {
            "status": "success",
            "as_of": today.isoformat(),
            "window_days": window,
            "expiring_soon_count": len(expiring_soon),
            "expired_count": len(expired),
            "expiring_soon": expiring_soon,
            "expired": expired,
        }

    finally:
        # Always close the session to prevent database lockups
        db.close()
