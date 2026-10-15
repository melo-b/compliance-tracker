from datetime import timedelta

from app.models.standard import WorkflowStatus
from app.services.dashboard import build_summary
from tests.helpers import in_days, today

SUMMARY = "/api/v1/dashboard/summary"
P, D, F = WorkflowStatus.PENDING, WorkflowStatus.DRAFT, WorkflowStatus.FINAL


def summary(client, headers, **params):
    response = client.get(SUMMARY, params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_an_empty_database_gives_zeros_for_every_key(client, readonly_headers):
    body = summary(client, readonly_headers)

    assert body["totals"] == {"products": 0, "standards": 0, "compliance_records": 0}
    assert body["by_workflow"] == {"Pending": 0, "Draft": 0, "Final": 0}
    assert body["by_validity"] == {"Valid": 0, "Expiring Soon": 0, "Expired": 0}
    assert body["expiring_soon"] == [] and body["expired"] == []
    assert body["as_of"] == str(today())
    assert body["expiring_soon_days"] == 90


def test_counts_by_workflow_and_validity(client, readonly_headers, make_compliance):
    make_compliance(P)
    make_compliance(D, expiration_date=in_days(5))  # no validity until it is final
    make_compliance(F, expiration_date=None)  # valid, no expiry
    make_compliance(F, expiration_date=in_days(400))  # valid
    make_compliance(F, expiration_date=in_days(30))  # expiring soon
    make_compliance(F, expiration_date=in_days(0))  # expiring soon (the expiry day)
    make_compliance(F, expiration_date=in_days(-1))  # expired

    body = summary(client, readonly_headers)

    assert body["by_workflow"] == {"Pending": 1, "Draft": 1, "Final": 5}
    assert body["by_validity"] == {"Valid": 2, "Expiring Soon": 2, "Expired": 1}
    assert sum(body["by_validity"].values()) == body["by_workflow"]["Final"]
    assert body["totals"]["compliance_records"] == 7
    assert body["totals"]["products"] == 7 and body["totals"]["standards"] == 7


def test_expiring_soon_is_ordered_soonest_first_and_excludes_everything_else(
    client, readonly_headers, make_compliance
):
    later = make_compliance(F, expiration_date=in_days(60))
    sooner = make_compliance(F, expiration_date=in_days(3))
    make_compliance(F, expiration_date=in_days(200))  # outside the window
    make_compliance(F, expiration_date=in_days(-5))  # already expired
    make_compliance(D, expiration_date=in_days(3))  # not issued

    body = summary(client, readonly_headers)

    assert [r["id"] for r in body["expiring_soon"]] == [sooner.id, later.id]


def test_expired_lists_the_most_recently_expired_first(client, readonly_headers, make_compliance):
    long_ago = make_compliance(F, expiration_date=in_days(-300))
    yesterday = make_compliance(F, expiration_date=in_days(-1))

    body = summary(client, readonly_headers)

    assert [r["id"] for r in body["expired"]] == [yesterday.id, long_ago.id]


def test_list_length_is_limited(client, readonly_headers, make_compliance):
    for offset in range(1, 8):
        make_compliance(F, expiration_date=in_days(offset))

    body = summary(client, readonly_headers, limit=3)

    assert len(body["expiring_soon"]) == 3
    assert body["by_validity"]["Expiring Soon"] == 7  # the counts are not limited


def test_entries_include_product_and_standard_details(client, readonly_headers, make_compliance):
    record = make_compliance(F, expiration_date=in_days(10), certificate_number="C-1")

    entry = summary(client, readonly_headers)["expiring_soon"][0]

    assert entry["product"]["model_number"] == record.product.model_number
    assert entry["standard"]["standard_number"] == record.standard.standard_number
    assert entry["validity"] == "Expiring Soon" and entry["days_until_expiry"] == 10


def test_invalid_limit_is_rejected(client, readonly_headers):
    for limit in (0, 51):
        assert (
            client.get(SUMMARY, params={"limit": limit}, headers=readonly_headers).status_code
            == 422
        )


def test_the_window_boundary_is_inclusive_for_a_given_date(db_session, make_compliance):
    """build_summary takes the date as input, so the boundary can be tested exactly."""
    fixed_today = today()
    make_compliance(F, expiration_date=fixed_today + timedelta(days=90))  # last day in the window
    make_compliance(F, expiration_date=fixed_today + timedelta(days=91))  # first day outside

    result = build_summary(db_session, today=fixed_today)

    assert result.by_validity == {"Valid": 1, "Expiring Soon": 1, "Expired": 0}
