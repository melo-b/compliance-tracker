import json

import pytest

from app.models.standard import ProductCompliance, WorkflowStatus
from app.worker.tasks import scan_expiring_compliance_records
from tests.helpers import in_days

FINAL = WorkflowStatus.FINAL


@pytest.fixture(autouse=True)
def worker_uses_the_test_database(monkeypatch, db_session):
    """The task opens its own session; point it at the in-memory test database."""
    monkeypatch.setattr("app.worker.tasks.SessionLocal", lambda: db_session)


def ids(report, key):
    return [item["id"] for item in report[key]]


def test_report_lists_expiring_and_expired_final_certificates(make_compliance):
    expired = make_compliance(FINAL, expiration_date=in_days(-3))
    expiring = make_compliance(FINAL, expiration_date=in_days(20))
    healthy = make_compliance(FINAL, expiration_date=in_days(400))

    report = scan_expiring_compliance_records()

    assert report["status"] == "success"
    assert ids(report, "expired") == [expired.id]
    assert ids(report, "expiring_soon") == [expiring.id]
    assert healthy.id not in ids(report, "expired") + ids(report, "expiring_soon")
    assert (report["expired_count"], report["expiring_soon_count"]) == (1, 1)


def test_only_final_certificates_are_reported(make_compliance):
    make_compliance(WorkflowStatus.PENDING, expiration_date=in_days(-30))
    make_compliance(WorkflowStatus.DRAFT, expiration_date=in_days(5))

    report = scan_expiring_compliance_records()

    assert (report["expired_count"], report["expiring_soon_count"]) == (0, 0)


def test_certificates_without_an_expiry_date_are_never_reported(make_compliance):
    make_compliance(FINAL, expiration_date=None)

    report = scan_expiring_compliance_records()

    assert (report["expired_count"], report["expiring_soon_count"]) == (0, 0)


@pytest.mark.parametrize(
    ("offset", "bucket"),
    [(-1, "expired"), (0, "expiring_soon"), (90, "expiring_soon"), (91, None)],
)
def test_the_default_window_is_90_days_inclusive(make_compliance, offset, bucket):
    record = make_compliance(FINAL, expiration_date=in_days(offset))

    report = scan_expiring_compliance_records()

    for name in ("expired", "expiring_soon"):
        assert (record.id in ids(report, name)) == (name == bucket)
    assert report["window_days"] == 90


def test_the_window_can_be_overridden(make_compliance):
    record = make_compliance(FINAL, expiration_date=in_days(45))

    assert ids(scan_expiring_compliance_records(days_threshold=30), "expiring_soon") == []
    assert ids(scan_expiring_compliance_records(days_threshold=60), "expiring_soon") == [record.id]


def test_the_scan_never_changes_any_record(make_compliance, db_session):
    expired = make_compliance(FINAL, expiration_date=in_days(-10))
    expiring = make_compliance(FINAL, expiration_date=in_days(10))
    draft = make_compliance(WorkflowStatus.DRAFT, expiration_date=in_days(-10))
    before = {r.id: (r.workflow_status, r.expiration_date) for r in (expired, expiring, draft)}

    scan_expiring_compliance_records()

    after = {
        r.id: (r.workflow_status, r.expiration_date)
        for r in db_session.query(ProductCompliance).all()
    }
    assert after == before


def test_the_report_is_ordered_by_expiry_and_json_serialisable(make_compliance):
    later = make_compliance(FINAL, expiration_date=in_days(60), certificate_number="B")
    sooner = make_compliance(FINAL, expiration_date=in_days(5), certificate_number="A")

    report = scan_expiring_compliance_records()

    assert ids(report, "expiring_soon") == [sooner.id, later.id]
    first = report["expiring_soon"][0]
    assert first["certificate_number"] == "A"
    assert first["days_until_expiry"] == 5
    json.dumps(report)  # Celery's JSON result backend must be able to store it
