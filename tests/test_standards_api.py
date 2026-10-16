"""Standards CRUD, filters and cascades (these had no tests before Phase 4)."""

import pytest

from app.models.standard import ProductCompliance, Standard, StandardStatus

STANDARDS = "/api/v1/standards/"


@pytest.fixture
def catalogue(db_session):
    db_session.add_all(
        [
            Standard(
                standard_number="UL 508", title="Industrial Control Equipment", issuing_body="UL"
            ),
            Standard(
                standard_number="CSA C22.2 No. 14",
                title="Industrial Control Equipment",
                issuing_body="CSA Group",
            ),
            Standard(
                standard_number="IEC 60947-1",
                title="Low-voltage switchgear",
                issuing_body="IEC",
                status=StandardStatus.RETIRED,
            ),
        ]
    )
    db_session.commit()


def numbers(response):
    assert response.status_code == 200, response.text
    return [s["standard_number"] for s in response.json()["items"]]


def test_admin_creates_a_standard(client, admin_headers):
    response = client.post(
        STANDARDS,
        json={
            "standard_number": "UL 508",
            "title": "Industrial Control Equipment",
            "issuing_body": "UL",
        },
        headers=admin_headers,
    )

    assert response.status_code == 201
    assert response.json()["status"] == "Active"  # the default


def test_standards_are_listed_by_number_by_default(client, readonly_headers, catalogue):
    assert numbers(client.get(STANDARDS, headers=readonly_headers)) == [
        "CSA C22.2 No. 14",
        "IEC 60947-1",
        "UL 508",
    ]


def test_filter_by_status_and_issuing_body_and_search(client, readonly_headers, catalogue):
    assert numbers(client.get(f"{STANDARDS}?status=Retired", headers=readonly_headers)) == [
        "IEC 60947-1"
    ]
    assert numbers(client.get(f"{STANDARDS}?issuing_body=csa", headers=readonly_headers)) == [
        "CSA C22.2 No. 14"
    ]
    assert numbers(
        client.get(f"{STANDARDS}?q=control&sort=-standard_number", headers=readonly_headers)
    ) == ["UL 508", "CSA C22.2 No. 14"]
    assert client.get(f"{STANDARDS}?status=Bogus", headers=readonly_headers).status_code == 422


def test_update_changes_only_the_fields_sent(client, admin_headers, catalogue, db_session):
    standard = db_session.query(Standard).filter_by(standard_number="UL 508").one()

    response = client.patch(
        f"{STANDARDS}{standard.id}", json={"title": "New title"}, headers=admin_headers
    )

    assert response.status_code == 200
    assert response.json()["title"] == "New title"
    assert response.json()["issuing_body"] == "UL"


def test_an_explicit_null_cannot_blank_a_required_field(
    client, admin_headers, catalogue, db_session
):
    standard = db_session.query(Standard).filter_by(standard_number="UL 508").one()

    response = client.patch(
        f"{STANDARDS}{standard.id}",
        json={"title": None, "issuing_body": None},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Industrial Control Equipment"


def test_renumbering_onto_an_existing_number_is_a_conflict(
    client, admin_headers, catalogue, db_session
):
    standard = db_session.query(Standard).filter_by(standard_number="UL 508").one()

    response = client.patch(
        f"{STANDARDS}{standard.id}", json={"standard_number": "IEC 60947-1"}, headers=admin_headers
    )

    assert response.status_code == 409


def test_keeping_the_same_number_on_update_is_fine(client, admin_headers, catalogue, db_session):
    standard = db_session.query(Standard).filter_by(standard_number="UL 508").one()

    response = client.patch(
        f"{STANDARDS}{standard.id}",
        json={"standard_number": "UL 508", "title": "X"},
        headers=admin_headers,
    )

    assert response.status_code == 200


def test_deleting_a_standard_removes_its_compliance_records(
    client, admin_headers, make_compliance, db_session
):
    record = make_compliance()

    response = client.delete(f"{STANDARDS}{record.standard_id}", headers=admin_headers)

    assert response.status_code == 204
    assert db_session.query(ProductCompliance).count() == 0


def test_deleting_a_missing_standard_is_404(client, admin_headers):
    assert client.delete(f"{STANDARDS}9999", headers=admin_headers).status_code == 404


def test_compliance_records_can_be_deleted_by_admins_only(
    client, admin_headers, engineer_headers, make_compliance
):
    record = make_compliance()
    url = f"{STANDARDS}compliance/{record.id}"

    assert client.delete(url, headers=engineer_headers).status_code == 403
    assert client.delete(url, headers=admin_headers).status_code == 204
    assert client.delete(url, headers=admin_headers).status_code == 404
