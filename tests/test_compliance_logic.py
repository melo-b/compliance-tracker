"""The certification rules as pure functions: validity and workflow transitions."""

from datetime import date, timedelta

import pytest

from app.models.standard import WorkflowStatus
from app.models.user import UserRole
from app.services.compliance_logic import (
    InvalidTransitionError,
    TransitionNotPermittedError,
    Validity,
    check_transition,
    compute_validity,
    days_until_expiry,
)

TODAY = date(2026, 6, 15)
FINAL = WorkflowStatus.FINAL


def on(offset_days: int) -> date:
    return TODAY + timedelta(days=offset_days)


# --- validity ---


@pytest.mark.parametrize(
    ("expiration_date", "expected"),
    [
        (None, Validity.VALID),  # final, never expires: "Valid - No expiry"
        (on(-365), Validity.EXPIRED),
        (on(-1), Validity.EXPIRED),  # expired yesterday
        (on(0), Validity.EXPIRING_SOON),  # the expiry day itself is still a valid day
        (on(1), Validity.EXPIRING_SOON),
        (on(89), Validity.EXPIRING_SOON),
        (on(90), Validity.EXPIRING_SOON),  # the 90-day window includes its last day
        (on(91), Validity.VALID),
        (on(365), Validity.VALID),
    ],
)
def test_validity_of_a_final_certificate(expiration_date, expected):
    assert compute_validity(FINAL, expiration_date, TODAY, 90) == expected


@pytest.mark.parametrize("status", [WorkflowStatus.PENDING, WorkflowStatus.DRAFT])
@pytest.mark.parametrize("expiration_date", [None, on(-30), on(10), on(500)])
def test_records_that_are_not_final_have_no_validity(status, expiration_date):
    """Nothing has been issued yet, whatever date happens to be filled in."""
    assert compute_validity(status, expiration_date, TODAY, 90) is None


def test_the_window_is_configurable_per_call():
    assert compute_validity(FINAL, on(45), TODAY, 30) == Validity.VALID
    assert compute_validity(FINAL, on(45), TODAY, 60) == Validity.EXPIRING_SOON


def test_the_default_window_is_90_days():
    assert compute_validity(FINAL, on(90), TODAY) == Validity.EXPIRING_SOON
    assert compute_validity(FINAL, on(91), TODAY) == Validity.VALID


def test_validity_values_match_the_api_labels():
    assert [v.value for v in Validity] == ["Valid", "Expiring Soon", "Expired"]


# --- days until expiry ---


@pytest.mark.parametrize(
    ("expiration_date", "expected"),
    [(None, None), (on(0), 0), (on(30), 30), (on(-5), -5)],
)
def test_days_until_expiry(expiration_date, expected):
    assert days_until_expiry(expiration_date, TODAY) == expected


# --- workflow transitions ---

P, D, F = WorkflowStatus.PENDING, WorkflowStatus.DRAFT, WorkflowStatus.FINAL
ADMIN, ENGINEER = UserRole.ADMIN, UserRole.ENGINEER


@pytest.mark.parametrize("role", [ADMIN, ENGINEER])
@pytest.mark.parametrize(("current", "target"), [(P, D), (D, F)])
def test_everyone_who_can_edit_may_move_forward_one_step(role, current, target):
    check_transition(current, target, role)  # does not raise


@pytest.mark.parametrize("role", [ADMIN, ENGINEER])
def test_skipping_a_step_is_rejected_for_everyone(role):
    with pytest.raises(InvalidTransitionError, match="Cannot skip from Pending to Final"):
        check_transition(P, F, role)


@pytest.mark.parametrize("role", [ADMIN, ENGINEER])
@pytest.mark.parametrize("status", [P, D, F])
def test_moving_to_the_current_status_is_rejected(role, status):
    with pytest.raises(InvalidTransitionError, match="already"):
        check_transition(status, status, role)


@pytest.mark.parametrize(("current", "target"), [(F, D), (D, P), (F, P)])
def test_admin_may_move_backward(current, target):
    check_transition(current, target, ADMIN)  # does not raise


@pytest.mark.parametrize(("current", "target"), [(F, D), (D, P), (F, P)])
def test_engineer_may_not_move_backward(current, target):
    with pytest.raises(TransitionNotPermittedError, match="Only an admin"):
        check_transition(current, target, ENGINEER)


def test_read_only_users_are_never_permitted_to_move_backward():
    with pytest.raises(TransitionNotPermittedError):
        check_transition(F, D, UserRole.READ_ONLY)
