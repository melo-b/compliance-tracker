"""Consistent error responses, and the database as the final guard against duplicates."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.product import Product
from app.models.standard import ProductCompliance, Standard, WorkflowStatus

PRODUCTS = "/api/v1/products/"
STANDARDS = "/api/v1/standards/"
COMPLIANCE = "/api/v1/standards/compliance/"


# --- every application error has the same shape: {"detail": ..., "code": ...} ---


@pytest.mark.parametrize(
    ("path", "code"),
    [
        (f"{PRODUCTS}9999", "not_found"),
        (f"{STANDARDS}9999", "not_found"),
        ("/api/v1/documents/9999", "not_found"),
    ],
)
def test_missing_things_are_404_with_a_code(client, readonly_headers, path, code):
    response = client.get(path, headers=readonly_headers)

    assert response.status_code == 404
    assert set(response.json()) == {"detail", "code"}
    assert response.json()["code"] == code


def test_duplicates_are_409_conflicts(client, engineer_headers, admin_headers):
    product = {"name": "Relay", "model_number": "R-1"}
    standard = {"standard_number": "UL 508", "title": "T", "issuing_body": "UL"}
    client.post(PRODUCTS, json=product, headers=engineer_headers)
    client.post(STANDARDS, json=standard, headers=admin_headers)

    for path, body, headers in (
        (PRODUCTS, product, engineer_headers),
        (STANDARDS, standard, admin_headers),
    ):
        response = client.post(path, json=body, headers=headers)
        assert response.status_code == 409
        assert response.json()["code"] == "conflict"


def test_registering_an_existing_email_is_a_409(client, make_user):
    make_user(email="taken@example.com")

    response = client.post(
        "/api/v1/auth/register/",
        json={"email": "taken@example.com", "password": "a-long-password-123"},
    )

    assert response.status_code == 409 and response.json()["code"] == "conflict"


def test_rule_violations_are_422_with_a_code(client, engineer_headers, make_compliance):
    record = make_compliance(WorkflowStatus.FINAL, issued_date=None, expiration_date=None)

    response = client.patch(
        f"{COMPLIANCE}{record.id}",
        json={"issued_date": "2026-05-01", "expiration_date": "2026-01-01"},
        headers=engineer_headers,
    )

    assert response.status_code == 422  # rejected by validation before it reaches the service

    bad_sort = client.get(f"{PRODUCTS}?sort=nope", headers=engineer_headers)
    assert bad_sort.status_code == 422 and bad_sort.json()["code"] == "invalid_request"


def test_workflow_errors_carry_their_own_codes(client, engineer_headers, make_compliance):
    pending = make_compliance(WorkflowStatus.PENDING)
    final = make_compliance(WorkflowStatus.FINAL)

    skip = client.post(
        f"{COMPLIANCE}{pending.id}/transition", json={"target": "Final"}, headers=engineer_headers
    )
    back = client.post(
        f"{COMPLIANCE}{final.id}/transition", json={"target": "Draft"}, headers=engineer_headers
    )

    assert (skip.status_code, skip.json()["code"]) == (409, "invalid_transition")
    assert (back.status_code, back.json()["code"]) == (403, "transition_not_permitted")


def test_authentication_errors_keep_their_standard_shape(client):
    response = client.get(PRODUCTS)
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


# --- the unique constraint ---


def test_the_database_itself_rejects_a_duplicate_mapping(db_session, make_compliance):
    """The API checks first, but only the database can stop two simultaneous requests."""
    existing = make_compliance()
    db_session.add(
        ProductCompliance(product_id=existing.product_id, standard_id=existing.standard_id)
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_a_lost_race_on_a_mapping_is_still_a_clean_409(
    client, engineer_headers, make_compliance, db_session, monkeypatch
):
    """Simulate the in-code duplicate check missing a record that another request just created."""
    existing = make_compliance()
    monkeypatch.setattr(db_session, "scalar", lambda *args, **kwargs: None)

    response = client.post(
        COMPLIANCE,
        json={"product_id": existing.product_id, "standard_id": existing.standard_id},
        headers=engineer_headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Product is already mapped to this standard"


def test_a_lost_race_on_a_model_number_is_still_a_clean_409(
    client, engineer_headers, db_session, monkeypatch
):
    db_session.add(Product(name="Existing", model_number="R-1"))
    db_session.commit()
    monkeypatch.setattr(db_session, "scalar", lambda *args, **kwargs: None)

    response = client.post(
        PRODUCTS, json={"name": "New", "model_number": "R-1"}, headers=engineer_headers
    )

    assert response.status_code == 409 and response.json()["code"] == "conflict"


def test_a_lost_race_on_a_standard_number_is_still_a_clean_409(
    client, admin_headers, db_session, monkeypatch
):
    db_session.add(Standard(standard_number="UL 508", title="T", issuing_body="UL"))
    db_session.commit()
    monkeypatch.setattr(db_session, "scalar", lambda *args, **kwargs: None)

    response = client.post(
        STANDARDS,
        json={"standard_number": "UL 508", "title": "Other", "issuing_body": "UL"},
        headers=admin_headers,
    )

    assert response.status_code == 409


def test_different_products_may_share_a_standard(
    client, engineer_headers, make_compliance, db_session
):
    first = make_compliance()
    other = Product(name="Other", model_number="O-1")
    db_session.add(other)
    db_session.commit()

    response = client.post(
        COMPLIANCE,
        json={"product_id": other.id, "standard_id": first.standard_id},
        headers=engineer_headers,
    )

    assert response.status_code == 201
