"""Business rules for certification records: validity and workflow transitions.

Everything here is a pure function of its arguments (no database access, no hidden clock
unless `today` is omitted), which keeps the rules easy to test exhaustively.
"""
import enum
from datetime import UTC, date, datetime

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.standard import WorkflowStatus
from app.models.user import UserRole


class Validity(enum.StrEnum):
    """Computed state of a *final* certificate. Never stored in the database."""

    VALID = "Valid"
    EXPIRING_SOON = "Expiring Soon"
    EXPIRED = "Expired"


def utc_today() -> date:
    return datetime.now(UTC).date()


def days_until_expiry(expiration_date: date | None, today: date | None = None) -> int | None:
    """Days from today until expiry (negative once expired); None when there is no expiry."""
    if expiration_date is None:
        return None
    return (expiration_date - (today or utc_today())).days


def compute_validity(
    workflow_status: WorkflowStatus,
    expiration_date: date | None,
    today: date | None = None,
    expiring_soon_days: int | None = None,
) -> Validity | None:
    """Validity of a certification record.

    - Not final yet (Pending / Draft): no validity, nothing has been issued.
    - Final with no expiration date: Valid (it does not expire).
    - Final and past its expiration date: Expired.
    - Final and expiring within the window (inclusive of the expiry day): Expiring Soon.
    - Otherwise: Valid.
    """
    if workflow_status != WorkflowStatus.FINAL:
        return None

    days_left = days_until_expiry(expiration_date, today)
    if days_left is None:
        return Validity.VALID
    if days_left < 0:
        return Validity.EXPIRED

    window = get_settings().expiring_soon_days if expiring_soon_days is None else expiring_soon_days
    return Validity.EXPIRING_SOON if days_left <= window else Validity.VALID


# ==========================================
# WORKFLOW TRANSITIONS
# ==========================================
_ORDER = [WorkflowStatus.PENDING, WorkflowStatus.DRAFT, WorkflowStatus.FINAL]


class WorkflowError(AppError):
    """Base class for rejected workflow transitions."""


class InvalidTransitionError(WorkflowError):
    """The requested move is not allowed from the current status."""

    status_code = 409
    code = "invalid_transition"


class TransitionNotPermittedError(WorkflowError):
    """The user's role may not make this move."""

    status_code = 403
    code = "transition_not_permitted"


def check_transition(current: WorkflowStatus, target: WorkflowStatus, role: UserRole) -> None:
    """Raises unless `role` may move a record from `current` to `target`.

    Engineers and admins move forward exactly one step (Pending -> Draft -> Final). Only admins
    may move backward, by any number of steps, to correct mistakes.
    """
    if target == current:
        raise InvalidTransitionError(f"The record is already {current.value}")

    step = _ORDER.index(target) - _ORDER.index(current)

    if step > 1:
        raise InvalidTransitionError(
            f"Cannot skip from {current.value} to {target.value}; "
            f"move to {_ORDER[_ORDER.index(current) + 1].value} first"
        )

    if step < 0 and role != UserRole.ADMIN:
        raise TransitionNotPermittedError("Only an admin can move a record backward")
