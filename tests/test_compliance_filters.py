"""Filtering compliance records, including that the SQL validity filter matches the Python rule."""

import pytest
from sqlalchemy import event

from app.models.standard import WorkflowStatus
from app.services.compliance_logic import Validity, compute_validity
from tests.helpers import in_days

COMPLIANCE = "/api/v1/standards/compliance/"
P, D, F = WorkflowStatus.PENDING, WorkflowStatus.DRAFT, WorkflowStatus.FINAL


def ids(response):
    assert response.status_code == 200, response.text
    return sorted(item["id"] for item in response.json()["items"])


def get(client, headers, **params):
    return client.get(COMPLIANCE, params=params, headers=headers)


# --- the SQL filter and compute_validity must agree on every boundary ---

OFFSETS = [None, -400, -2, -1, 0, 1, 30, 89, 90, 91, 92, 400]


@pytest.fixture
def grid(make_compliance):
    """One record for every (workflow status, expiry offset) combination."""
    return [
        (
            make_compliance(status, expiration_date=None if offset is None else in_days(offset)),
            offset,
        )
        for status in (P, D, F)
        for offset in OFFSETS
    ]


@pytest.mark.parametrize("validity", list(Validity))
def test_validity_filter_matches_compute_validity_for_every_boundary(
    client, readonly_headers, grid, validity
):
    expected = sorted(
        record.id
        for record, _ in grid
        if compute_validity(record.workflow_status, record.expiration_date) == validity
    )

    assert expected  # the grid really contains records of this validity
    assert ids(get(client, readonly_headers, validity=validity.value, limit=200)) == expected


def test_the_three_validities_never_overlap_and_only_cover_final_records(
    client, readonly_headers, grid
):
    found = {
        v: set(ids(get(client, readonly_headers, validity=v.value, limit=200))) for v in Validity
    }

    assert not (found[Validity.VALID] & found[Validity.EXPIRING_SOON])
    assert not (found[Validity.VALID] & found[Validity.EXPIRED])
    assert not (found[Validity.EXPIRING_SOON] & found[Validity.EXPIRED])
    final_ids = {r.id for r, _ in grid if r.workflow_status == F}
    assert (
        found[Validity.VALID] | found[Validity.EXPIRING_SOON] | found[Validity.EXPIRED] == final_ids
    )


def test_validity_with_a_space_in_its_name_works_in_a_url(
    client, readonly_headers, make_compliance
):
    record = make_compliance(F, expiration_date=in_days(10))
    assert ids(client.get(f"{COMPLIANCE}?validity=Expiring%20Soon", headers=readonly_headers)) == [
        record.id
    ]


def test_unknown_validity_is_rejected(client, readonly_headers):
    assert get(client, readonly_headers, validity="Mostly Fine").status_code == 422


# --- other filters ---


def test_filter_by_workflow_status(client, readonly_headers, make_compliance):
    pending, draft, final = make_compliance(P), make_compliance(D), make_compliance(F)

    assert ids(get(client, readonly_headers, workflow_status="Draft")) == [draft.id]
    assert ids(get(client, readonly_headers, workflow_status="Final")) == [final.id]
    assert ids(get(client, readonly_headers)) == sorted([pending.id, draft.id, final.id])


def test_filter_by_product_and_standard(client, readonly_headers, make_compliance):
    first, second = make_compliance(), make_compliance()

    assert ids(get(client, readonly_headers, product_id=first.product_id)) == [first.id]
    assert ids(get(client, readonly_headers, standard_id=second.standard_id)) == [second.id]
    assert (
        ids(
            get(
                client,
                readonly_headers,
                product_id=first.product_id,
                standard_id=second.standard_id,
            )
        )
        == []
    )  # filters combine with AND


def test_expiring_within_days_means_not_yet_expired_but_soon(
    client, readonly_headers, make_compliance
):
    today_ = make_compliance(F, expiration_date=in_days(0))
    in_ten = make_compliance(F, expiration_date=in_days(10))
    in_fifty = make_compliance(F, expiration_date=in_days(50))
    make_compliance(F, expiration_date=in_days(-1))  # already expired
    make_compliance(F, expiration_date=None)  # never expires
    make_compliance(D, expiration_date=in_days(5))  # not issued yet

    assert ids(get(client, readonly_headers, expiring_within_days=10)) == sorted(
        [today_.id, in_ten.id]
    )
    assert ids(get(client, readonly_headers, expiring_within_days=50)) == sorted(
        [today_.id, in_ten.id, in_fifty.id]
    )
    assert ids(get(client, readonly_headers, expiring_within_days=0)) == [today_.id]


def test_filters_combine(client, readonly_headers, make_compliance):
    keep = make_compliance(F, expiration_date=in_days(20), agency="CSA Group")
    make_compliance(F, expiration_date=in_days(20), agency="UL")

    result = get(client, readonly_headers, validity="Expiring Soon", q="csa")

    assert ids(result) == [keep.id]
    assert result.json()["total"] == 1


def test_search_matches_certificate_number_or_agency(client, readonly_headers, make_compliance):
    by_number = make_compliance(certificate_number="REG-4411")
    by_agency = make_compliance(agency="Lloyd Register")
    make_compliance(certificate_number="X-9", agency="UL")

    assert ids(get(client, readonly_headers, q="reg")) == sorted([by_number.id, by_agency.id])


def test_negative_expiry_window_is_rejected(client, readonly_headers):
    assert get(client, readonly_headers, expiring_within_days=-1).status_code == 422


# --- responses carry what a UI needs without extra requests ---


def test_items_embed_the_product_and_standard(client, readonly_headers, make_compliance):
    record = make_compliance(F)

    item = get(client, readonly_headers).json()["items"][0]

    assert item["product"] == {
        "id": record.product_id,
        "name": record.product.name,
        "model_number": record.product.model_number,
    }
    assert item["standard"]["standard_number"] == record.standard.standard_number


def test_listing_does_not_run_a_query_per_row(
    client, readonly_headers, make_compliance, db_session
):
    """Embedding product/standard must not turn a list into N+1 queries."""
    for _ in range(15):
        make_compliance(F, expiration_date=in_days(10))

    statements = []
    engine = db_session.get_bind()

    def count(conn, cursor, statement, *args):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", count)
    try:
        assert get(client, readonly_headers, limit=50).json()["total"] == 15
    finally:
        event.remove(engine, "before_cursor_execute", count)

    selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
    assert len(selects) <= 6, f"{len(selects)} queries for 15 rows:\n" + "\n".join(selects)
