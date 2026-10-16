from types import SimpleNamespace

import pytest
from kombu.exceptions import OperationalError

from app.models.standard import WorkflowStatus
from tests.helpers import in_days

COMPLIANCE = "/api/v1/standards/compliance/"


def transition(client, record_id, target, headers):
    return client.post(
        f"{COMPLIANCE}{record_id}/transition", json={"target": target}, headers=headers
    )


@pytest.fixture
def product_and_standard(client, engineer_headers, admin_headers):
    product = client.post(
        "/api/v1/products/",
        json={"model_number": "RELAY-100", "name": "High Voltage Relay"},
        headers=engineer_headers,
    ).json()
    standard = client.post(
        "/api/v1/standards/",
        json={
            "standard_number": "UL 508",
            "title": "Industrial Control Equipment",
            "issuing_body": "UL",
        },
        headers=admin_headers,
    ).json()
    return product["id"], standard["id"]


# --- creating records ---


def test_new_records_start_pending_and_have_no_validity(
    client, engineer_headers, product_and_standard
):
    product_id, standard_id = product_and_standard

    response = client.post(
        COMPLIANCE,
        json={"product_id": product_id, "standard_id": standard_id},
        headers=engineer_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["workflow_status"] == "Pending"
    assert body["validity"] is None
    assert body["days_until_expiry"] is None


def test_certificate_details_are_stored(client, engineer_headers, product_and_standard):
    product_id, standard_id = product_and_standard

    body = client.post(
        COMPLIANCE,
        json={
            "product_id": product_id,
            "standard_id": standard_id,
            "certificate_number": "  LR 12345  ",
            "agency": "CSA Group",
            "issued_date": str(in_days(-10)),
            "expiration_date": str(in_days(355)),
        },
        headers=engineer_headers,
    ).json()

    assert body["certificate_number"] == "LR 12345"  # surrounding whitespace is trimmed
    assert body["agency"] == "CSA Group"
    assert body["issued_date"] == str(in_days(-10))


def test_a_status_cannot_be_chosen_when_creating(client, engineer_headers, product_and_standard):
    product_id, standard_id = product_and_standard

    response = client.post(
        COMPLIANCE,
        json={"product_id": product_id, "standard_id": standard_id, "workflow_status": "Final"},
        headers=engineer_headers,
    )

    assert response.status_code == 422


def test_expiry_before_issue_is_rejected(client, engineer_headers, product_and_standard):
    product_id, standard_id = product_and_standard

    response = client.post(
        COMPLIANCE,
        json={
            "product_id": product_id,
            "standard_id": standard_id,
            "issued_date": str(in_days(10)),
            "expiration_date": str(in_days(5)),
        },
        headers=engineer_headers,
    )

    assert response.status_code == 422


# --- computed validity in responses ---


@pytest.mark.parametrize(
    ("status", "expiry_offset", "validity", "days"),
    [
        (WorkflowStatus.FINAL, None, "Valid", None),  # "Valid - No expiry"
        (WorkflowStatus.FINAL, -1, "Expired", -1),
        (WorkflowStatus.FINAL, 0, "Expiring Soon", 0),
        (WorkflowStatus.FINAL, 30, "Expiring Soon", 30),
        (WorkflowStatus.FINAL, 90, "Expiring Soon", 90),
        (WorkflowStatus.FINAL, 91, "Valid", 91),
        (WorkflowStatus.DRAFT, 30, None, 30),
        (WorkflowStatus.PENDING, -30, None, -30),
    ],
)
def test_responses_include_computed_validity(
    client, readonly_headers, make_compliance, status, expiry_offset, validity, days
):
    expiry = None if expiry_offset is None else in_days(expiry_offset)
    record = make_compliance(status, expiration_date=expiry)

    body = client.get(f"{COMPLIANCE}product/{record.product_id}", headers=readonly_headers).json()[
        "items"
    ][0]

    assert body["validity"] == validity
    assert body["days_until_expiry"] == days


def test_validity_is_not_a_stored_column(make_compliance):
    assert not hasattr(make_compliance(), "validity")


# --- editing details ---


def test_engineer_can_edit_certificate_details(client, engineer_headers, make_compliance):
    record = make_compliance(WorkflowStatus.DRAFT)

    response = client.patch(
        f"{COMPLIANCE}{record.id}",
        json={"certificate_number": "LR 999", "agency": "UL", "expiration_date": str(in_days(200))},
        headers=engineer_headers,
    )

    assert response.status_code == 200
    assert response.json()["certificate_number"] == "LR 999"
    assert response.json()["workflow_status"] == "Draft"  # editing never moves the workflow


def test_the_workflow_status_cannot_be_changed_by_editing(
    client, engineer_headers, make_compliance
):
    record = make_compliance(WorkflowStatus.PENDING)

    response = client.patch(
        f"{COMPLIANCE}{record.id}", json={"workflow_status": "Final"}, headers=engineer_headers
    )

    assert response.status_code == 422
    assert (
        client.get(f"{COMPLIANCE}product/{record.product_id}", headers=engineer_headers).json()[
            "items"
        ][0]["workflow_status"]
        == "Pending"
    )


def test_editing_cannot_put_the_expiry_before_the_issue_date(
    client, engineer_headers, make_compliance
):
    record = make_compliance(
        WorkflowStatus.FINAL, issued_date=in_days(-30), expiration_date=in_days(300)
    )

    response = client.patch(
        f"{COMPLIANCE}{record.id}",
        json={"expiration_date": str(in_days(-60))},
        headers=engineer_headers,
    )

    assert response.status_code == 422


def test_renewing_an_expired_certificate_makes_it_valid_again(
    client, engineer_headers, make_compliance
):
    record = make_compliance(WorkflowStatus.FINAL, expiration_date=in_days(-5))

    renewed = client.patch(
        f"{COMPLIANCE}{record.id}",
        json={"expiration_date": str(in_days(365))},
        headers=engineer_headers,
    ).json()

    assert renewed["validity"] == "Valid"


def test_clearing_the_expiry_makes_a_final_certificate_valid_with_no_expiry(
    client, engineer_headers, make_compliance
):
    record = make_compliance(WorkflowStatus.FINAL, expiration_date=in_days(10))

    body = client.patch(
        f"{COMPLIANCE}{record.id}", json={"expiration_date": None}, headers=engineer_headers
    ).json()

    assert body["validity"] == "Valid"
    assert body["days_until_expiry"] is None


# --- workflow transitions ---


def test_engineer_walks_a_record_from_pending_to_final(client, engineer_headers, make_compliance):
    record = make_compliance(expiration_date=in_days(20))

    draft = transition(client, record.id, "Draft", engineer_headers)
    final = transition(client, record.id, "Final", engineer_headers)

    assert draft.status_code == 200 and draft.json()["workflow_status"] == "Draft"
    assert draft.json()["validity"] is None
    assert final.status_code == 200 and final.json()["workflow_status"] == "Final"
    assert final.json()["validity"] == "Expiring Soon"  # appears the moment it is final


def test_final_without_an_expiry_date_is_valid(client, engineer_headers, make_compliance):
    record = make_compliance(WorkflowStatus.DRAFT)

    body = transition(client, record.id, "Final", engineer_headers).json()

    assert body["validity"] == "Valid"
    assert body["days_until_expiry"] is None


def test_skipping_a_step_is_a_conflict(client, engineer_headers, make_compliance):
    record = make_compliance(WorkflowStatus.PENDING)

    response = transition(client, record.id, "Final", engineer_headers)

    assert response.status_code == 409
    assert "Cannot skip" in response.json()["detail"]


def test_repeating_the_current_status_is_a_conflict(client, engineer_headers, make_compliance):
    record = make_compliance(WorkflowStatus.DRAFT)
    assert transition(client, record.id, "Draft", engineer_headers).status_code == 409


def test_engineers_cannot_move_a_record_backward(client, engineer_headers, make_compliance):
    record = make_compliance(WorkflowStatus.FINAL)

    response = transition(client, record.id, "Draft", engineer_headers)

    assert response.status_code == 403
    assert "Only an admin" in response.json()["detail"]


def test_admins_can_move_a_record_backward(client, admin_headers, make_compliance):
    record = make_compliance(WorkflowStatus.FINAL, expiration_date=in_days(10))

    to_draft = transition(client, record.id, "Draft", admin_headers)
    to_pending = transition(client, record.id, "Pending", admin_headers)

    assert to_draft.json()["workflow_status"] == "Draft"
    assert to_draft.json()["validity"] is None  # a reverted certificate is no longer issued
    assert to_pending.json()["workflow_status"] == "Pending"


def test_read_only_users_cannot_transition(client, readonly_headers, make_compliance):
    record = make_compliance()
    assert transition(client, record.id, "Draft", readonly_headers).status_code == 403


def test_transitioning_a_missing_record_is_404(client, engineer_headers):
    assert transition(client, 9999, "Draft", engineer_headers).status_code == 404


@pytest.mark.parametrize("body", [{"target": "Approved"}, {}, {"target": "Draft", "extra": 1}])
def test_invalid_transition_requests_are_rejected(client, engineer_headers, make_compliance, body):
    record = make_compliance()

    response = client.post(
        f"{COMPLIANCE}{record.id}/transition", json=body, headers=engineer_headers
    )

    assert response.status_code == 422


# --- expiry scan endpoint ---


def test_scan_returns_503_when_no_task_queue_is_available(client, admin_headers, monkeypatch):
    def broker_down(**kwargs):
        raise OperationalError("Connection refused")

    monkeypatch.setattr(
        "app.api.routes_standard.scan_expiring_compliance_records",
        SimpleNamespace(delay=broker_down),
    )

    response = client.post(f"{COMPLIANCE}scan/", headers=admin_headers)

    assert response.status_code == 503
    assert response.json()["detail"] == "The background task queue is not available"


def test_scan_is_queued_with_the_default_window(client, admin_headers, monkeypatch):
    calls = []

    def fake_delay(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(id="task-123")

    monkeypatch.setattr(
        "app.api.routes_standard.scan_expiring_compliance_records",
        SimpleNamespace(delay=fake_delay),
    )

    response = client.post(f"{COMPLIANCE}scan/", headers=admin_headers)

    assert response.status_code == 202
    assert response.json()["task_id"] == "task-123"
    assert calls == [{}]  # no explicit threshold: the worker uses EXPIRING_SOON_DAYS
