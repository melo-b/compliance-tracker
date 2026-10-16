"""Edge cases that the feature tests do not reach: failure paths, races and legacy data."""

import io

import pytest
from sqlalchemy.orm import Session

from app.api.routes_document import get_storage
from app.db.database import get_db
from app.main import app
from app.models.document import Document
from app.models.product import Product
from app.models.standard import Standard, WorkflowStatus
from app.models.user import UserRole
from app.scripts import create_admin
from app.services.documents import media_type_for
from app.services.storage import LocalStorage
from app.worker import tasks
from tests.helpers import TEST_PASSWORD, in_days

PDF = b"%PDF-1.7\n1 0 obj\n<< >>\nendobj\n%%EOF\n"


# --- the database session dependency ---


def test_get_db_yields_a_session_and_always_closes_it(monkeypatch):
    generator = get_db()
    session = next(generator)
    closed = []
    monkeypatch.setattr(session, "close", lambda: closed.append(True))

    assert isinstance(session, Session)
    with pytest.raises(StopIteration):
        next(generator)
    assert closed == [True]


def test_get_db_closes_the_session_even_when_the_request_fails(monkeypatch):
    generator = get_db()
    session = next(generator)
    closed = []
    monkeypatch.setattr(session, "close", lambda: closed.append(True))

    with pytest.raises(RuntimeError):
        generator.throw(RuntimeError("boom"))
    assert closed == [True]


def test_the_root_page_is_public(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to the Compliance Tracker"}


# --- the admin bootstrap script's interactive prompts ---


def prompts(monkeypatch, *answers):
    given = iter(answers)
    monkeypatch.setattr(create_admin.getpass, "getpass", lambda _prompt: next(given))


def test_cli_asks_for_the_password_twice_when_none_is_provided(db_session, monkeypatch, capsys):
    monkeypatch.setattr(create_admin, "SessionLocal", lambda: db_session)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    prompts(monkeypatch, TEST_PASSWORD, TEST_PASSWORD)

    assert create_admin.main(["--email", "typed@example.com"]) == 0
    assert "Admin created: typed@example.com" in capsys.readouterr().out


def test_cli_rejects_mismatched_passwords(db_session, monkeypatch, capsys):
    monkeypatch.setattr(create_admin, "SessionLocal", lambda: db_session)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    prompts(monkeypatch, TEST_PASSWORD, "something-else-entirely")

    assert create_admin.main(["--email", "typed@example.com"]) == 1
    assert "do not match" in capsys.readouterr().err


def test_cli_does_not_ask_for_a_password_when_promoting_an_existing_user(
    db_session, make_user, monkeypatch, capsys
):
    make_user(UserRole.READ_ONLY, email="existing@example.com")
    monkeypatch.setattr(create_admin, "SessionLocal", lambda: db_session)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    monkeypatch.setattr(create_admin.getpass, "getpass", lambda _p: pytest.fail("must not prompt"))

    assert create_admin.main(["--email", "existing@example.com"]) == 0
    assert "Admin promoted" in capsys.readouterr().out


# --- compliance records ---


def test_mapping_a_product_to_the_same_standard_twice_is_a_conflict(
    client, engineer_headers, make_compliance
):
    existing = make_compliance()
    body = {"product_id": existing.product_id, "standard_id": existing.standard_id}

    response = client.post("/api/v1/standards/compliance/", json=body, headers=engineer_headers)

    assert response.status_code == 409
    assert response.json()["detail"] == "Product is already mapped to this standard"


def test_mapping_needs_an_existing_product_and_standard(
    client, engineer_headers, make_compliance, db_session
):
    existing = make_compliance()
    url = "/api/v1/standards/compliance/"

    no_product = client.post(
        url,
        json={"product_id": 9999, "standard_id": existing.standard_id},
        headers=engineer_headers,
    )
    no_standard = client.post(
        url, json={"product_id": existing.product_id, "standard_id": 9999}, headers=engineer_headers
    )

    assert (no_product.status_code, no_product.json()["detail"]) == (404, "Product not found")
    assert (no_standard.status_code, no_standard.json()["detail"]) == (404, "Standard not found")


# --- products and standards: updates that collide ---


def test_updating_a_product_cannot_take_another_products_model_number(
    client, engineer_headers, db_session
):
    db_session.add_all(
        [Product(name="A", model_number="A-1"), Product(name="B", model_number="B-1")]
    )
    db_session.commit()
    second = db_session.query(Product).filter_by(model_number="B-1").one()

    response = client.patch(
        f"/api/v1/products/{second.id}", json={"model_number": "A-1"}, headers=engineer_headers
    )

    assert response.status_code == 409
    assert "another product" in response.json()["detail"]


def test_a_null_cannot_blank_a_required_product_field(client, engineer_headers, db_session):
    db_session.add(Product(name="Keep me", model_number="K-1"))
    db_session.commit()
    product = db_session.query(Product).one()

    response = client.patch(
        f"/api/v1/products/{product.id}", json={"name": None}, headers=engineer_headers
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Keep me"


def test_a_lost_race_when_renaming_a_product_is_still_a_clean_409(
    client, engineer_headers, db_session, monkeypatch
):
    db_session.add_all(
        [Product(name="A", model_number="A-1"), Product(name="B", model_number="B-1")]
    )
    db_session.commit()
    second = db_session.query(Product).filter_by(model_number="B-1").one()
    monkeypatch.setattr("app.services.products._model_number_in_use", lambda *a, **k: False)

    response = client.patch(
        f"/api/v1/products/{second.id}", json={"model_number": "A-1"}, headers=engineer_headers
    )

    assert response.status_code == 409 and response.json()["code"] == "conflict"


def test_a_lost_race_when_renumbering_a_standard_is_still_a_clean_409(
    client, admin_headers, db_session, monkeypatch
):
    db_session.add_all(
        [
            Standard(standard_number="UL 1", title="T", issuing_body="UL"),
            Standard(standard_number="UL 2", title="T", issuing_body="UL"),
        ]
    )
    db_session.commit()
    second = db_session.query(Standard).filter_by(standard_number="UL 2").one()
    monkeypatch.setattr("app.services.standards._number_in_use", lambda *a, **k: False)

    response = client.patch(
        f"/api/v1/standards/{second.id}", json={"standard_number": "UL 1"}, headers=admin_headers
    )

    assert response.status_code == 409


# --- sorting and listing ---


def test_a_blank_sort_falls_back_to_the_default_order(client, readonly_headers, db_session):
    db_session.add_all([Product(name="B", model_number="2"), Product(name="A", model_number="1")])
    db_session.commit()

    response = client.get("/api/v1/products/?sort=,", headers=readonly_headers)

    assert response.status_code == 200
    assert [p["model_number"] for p in response.json()["items"]] == ["2", "1"]  # by id


def test_user_list_filters(client, admin_headers, make_user):
    make_user(UserRole.ENGINEER, email="eng.one@example.com")
    make_user(UserRole.READ_ONLY, email="viewer@example.com")
    make_user(UserRole.READ_ONLY, email="old.viewer@example.com", is_active=False)

    def emails(**params):
        body = client.get("/api/v1/users/", params=params, headers=admin_headers).json()
        return sorted(u["email"] for u in body["items"])

    assert emails(q="VIEWER") == ["old.viewer@example.com", "viewer@example.com"]
    assert emails(role="engineer") == ["eng.one@example.com"]
    assert emails(is_active="false") == ["old.viewer@example.com"]
    assert emails(role="read_only", is_active="true") == ["viewer@example.com"]


# --- documents: failure handling and legacy rows ---


@pytest.fixture
def storage(client, tmp_path):
    local = LocalStorage(tmp_path / "uploads")
    app.dependency_overrides[get_storage] = lambda: local
    return local


def stored_files(storage):
    return [p for p in storage.base.rglob("*") if p.is_file()] if storage.base.exists() else []


def test_a_failed_database_insert_leaves_no_orphaned_file(
    client, storage, engineer_headers, db_session, monkeypatch
):
    db_session.add(Product(name="P", model_number="P-1"))
    db_session.commit()
    product = db_session.query(Product).one()

    def failing_commit():
        raise RuntimeError("database went away")

    monkeypatch.setattr(db_session, "commit", failing_commit)

    with pytest.raises(RuntimeError):
        client.post(
            "/api/v1/documents/upload/",
            data={"product_id": str(product.id)},
            files={"file": ("cert.pdf", io.BytesIO(PDF))},
            headers=engineer_headers,
        )

    assert stored_files(storage) == []


def test_documents_without_stored_metadata_still_download(
    client, storage, readonly_headers, db_session
):
    """Rows uploaded before Phase 4 have no content type or size."""
    db_session.add(Product(name="P", model_number="P-1"))
    db_session.commit()
    product = db_session.query(Product).one()
    storage.base.mkdir(parents=True)
    (storage.base / "legacy.pdf").write_bytes(PDF)
    db_session.add(Document(filename="legacy.pdf", file_path="legacy.pdf", product_id=product.id))
    db_session.commit()
    document = db_session.query(Document).one()

    response = client.get(f"/api/v1/documents/{document.id}/download", headers=readonly_headers)

    assert response.status_code == 200
    assert response.content == PDF
    assert response.headers["content-type"] == "application/pdf"  # guessed from the name
    assert "content-length" not in response.headers  # the size was never recorded


def test_media_type_falls_back_when_nothing_is_known():
    assert media_type_for(Document(filename="notes.pdf", file_path="k")) == "application/pdf"
    assert media_type_for(Document(filename="mystery", file_path="k")) == "application/octet-stream"
    declared = Document(filename="a.pdf", file_path="k", content_type="image/png")
    assert media_type_for(declared) == "image/png"


# --- the worker report ---


def test_the_report_refuses_a_record_that_has_no_expiration_date(make_compliance):
    record = make_compliance(WorkflowStatus.FINAL, expiration_date=None)

    with pytest.raises(ValueError, match="no expiration date"):
        tasks._describe(record, in_days(0))
