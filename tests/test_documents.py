"""Document uploads, downloads and storage, including hostile input."""

import io

import pytest

from app.api.routes_document import get_storage
from app.core.config import get_settings
from app.main import app
from app.models.document import Document
from app.models.product import Product
from app.models.standard import Standard
from app.services.documents import sanitize_filename
from app.services.storage import LocalStorage

PDF = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
ZIP = b"PK\x03\x04" + b"\x00" * 32  # .docx / .xlsx container

UPLOAD = "/api/v1/documents/upload/"
DOCUMENTS = "/api/v1/documents"


@pytest.fixture
def storage(client, tmp_path):
    """Every test stores files in its own temporary directory."""
    local = LocalStorage(tmp_path / "uploads")
    app.dependency_overrides[get_storage] = lambda: local
    return local


@pytest.fixture
def product(db_session):
    item = Product(name="Relay", model_number="R-1")
    db_session.add(item)
    db_session.commit()
    return item


def upload(client, headers, product_id, name="cert.pdf", content=PDF, standard_id=None):
    data = {"product_id": str(product_id)}
    if standard_id is not None:
        data["standard_id"] = str(standard_id)
    return client.post(
        UPLOAD, data=data, files={"file": (name, io.BytesIO(content))}, headers=headers
    )


def stored_files(storage):
    return [p for p in storage.base.rglob("*") if p.is_file()] if storage.base.exists() else []


# --- file names ---


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("report.pdf", "report.pdf"),
        ("../../etc/passwd.pdf", "passwd.pdf"),
        ("..\\..\\windows\\system32\\evil.pdf", "evil.pdf"),
        ("C:\\Users\\bob\\cert.pdf", "cert.pdf"),
        ("/absolute/path/cert.pdf", "cert.pdf"),
        ("my   cert  .pdf", "my cert .pdf"),
        ("a<b>c:d|e?.pdf", "a_b_c_d_e_.pdf"),
        ("null\x00byte.pdf", "null_byte.pdf"),
        ("tab\tand\nnewline.pdf", "tab_and_newline.pdf"),
        ("..", "document"),
        ("...", "document"),
        ("", "document"),
        (None, "document"),
        ("   ", "document"),
    ],
)
def test_filenames_are_sanitised(raw, expected):
    assert sanitize_filename(raw) == expected


def test_long_filenames_are_shortened_but_keep_their_extension():
    result = sanitize_filename("x" * 500 + ".pdf")
    assert len(result) <= 100 and result.endswith(".pdf")


def test_unicode_names_are_kept_readable():
    assert sanitize_filename("Zertifikat für Müller.pdf") == "Zertifikat für Müller.pdf"


# --- uploading ---


def test_engineer_uploads_a_pdf(client, storage, engineer_headers, product):
    response = upload(client, engineer_headers, product.id)

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "cert.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["size_bytes"] == len(PDF)
    assert body["download_url"] == f"/api/v1/documents/{body['id']}/download"
    assert "file_path" not in body  # the internal storage key is never exposed


def test_the_stored_name_is_random_and_contains_nothing_from_the_client(
    client, storage, engineer_headers, product, db_session
):
    upload(client, engineer_headers, product.id, name="../../secret/evil name.pdf")

    [path] = stored_files(storage)
    assert "evil" not in path.name and "secret" not in path.name
    assert path.parent == storage.base  # nothing escaped the storage folder
    assert path.suffix == ".pdf"
    assert db_session.query(Document).one().filename == "evil name.pdf"


@pytest.mark.parametrize(
    ("name", "content", "content_type"),
    [
        ("a.pdf", PDF, "application/pdf"),
        ("A.PDF", PDF, "application/pdf"),
        ("a.png", PNG, "image/png"),
        ("a.jpg", JPEG, "image/jpeg"),
        ("a.jpeg", JPEG, "image/jpeg"),
        ("a.docx", ZIP, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("a.xlsx", ZIP, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ],
)
def test_allowed_file_types(
    client, storage, engineer_headers, product, name, content, content_type
):
    response = upload(client, engineer_headers, product.id, name=name, content=content)

    assert response.status_code == 201
    assert response.json()["content_type"] == content_type


@pytest.mark.parametrize(
    "name",
    [
        "malware.exe",
        "page.html",
        "image.svg",
        "script.js",
        "archive.zip",
        "noextension",
        "evil.pdf.exe",
        ".pdf",
    ],
)
def test_other_file_types_are_rejected(client, storage, engineer_headers, product, name):
    response = upload(client, engineer_headers, product.id, name=name)

    assert response.status_code == 415
    assert response.json()["code"] == "unsupported_media_type"
    assert stored_files(storage) == []


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("fake.pdf", b"MZ\x90\x00 this is really a Windows program"),
        ("fake.png", PDF),  # a real PDF pretending to be a PNG
        ("fake.docx", PDF),
        ("fake.jpg", b"<html><script>alert(1)</script></html>"),
    ],
)
def test_contents_must_match_the_extension(
    client, storage, engineer_headers, product, name, content
):
    response = upload(client, engineer_headers, product.id, name=name, content=content)

    assert response.status_code == 415
    assert "do not match" in response.json()["detail"]
    assert stored_files(storage) == []


def test_empty_files_are_rejected(client, storage, engineer_headers, product):
    response = upload(client, engineer_headers, product.id, content=b"")

    assert response.status_code == 422
    assert stored_files(storage) == []


def test_oversized_files_are_rejected_and_leave_nothing_behind(
    client, storage, engineer_headers, product, monkeypatch
):
    monkeypatch.setattr(get_settings(), "max_upload_bytes", 2048)

    response = upload(client, engineer_headers, product.id, content=PDF + b"x" * 5000)

    assert response.status_code == 413
    assert response.json()["code"] == "payload_too_large"
    assert stored_files(storage) == []  # no partial file


def test_a_file_exactly_at_the_limit_is_accepted(
    client, storage, engineer_headers, product, monkeypatch
):
    content = PDF + b"x" * (2048 - len(PDF))
    monkeypatch.setattr(get_settings(), "max_upload_bytes", len(content))

    assert upload(client, engineer_headers, product.id, content=content).status_code == 201


def test_unknown_product_or_standard_is_404_and_stores_nothing(
    client, storage, engineer_headers, product
):
    assert upload(client, engineer_headers, 9999).status_code == 404
    assert upload(client, engineer_headers, product.id, standard_id=9999).status_code == 404
    assert stored_files(storage) == []


def test_a_document_can_reference_a_standard(
    client, storage, engineer_headers, product, db_session
):
    standard = Standard(standard_number="UL 508", title="T", issuing_body="UL")
    db_session.add(standard)
    db_session.commit()

    body = upload(client, engineer_headers, product.id, standard_id=standard.id).json()

    assert body["standard_id"] == standard.id


def test_read_only_users_cannot_upload(client, storage, readonly_headers, product):
    assert upload(client, readonly_headers, product.id).status_code == 403
    assert stored_files(storage) == []


# --- downloading ---


def test_download_returns_the_exact_bytes_as_an_attachment(
    client, storage, engineer_headers, readonly_headers, product
):
    document = upload(client, engineer_headers, product.id, content=PDF).json()

    response = client.get(document["download_url"], headers=readonly_headers)

    assert response.status_code == 200
    assert response.content == PDF
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert 'filename="cert.pdf"' in response.headers["content-disposition"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-length"] == str(len(PDF))


def test_downloads_are_always_attachments_even_for_images(
    client, storage, engineer_headers, product
):
    document = upload(client, engineer_headers, product.id, name="photo.png", content=PNG).json()

    response = client.get(document["download_url"], headers=engineer_headers)

    assert response.headers["content-disposition"].startswith(
        "attachment;"
    )  # never rendered inline


def test_unicode_filenames_download_correctly(client, storage, engineer_headers, product):
    document = upload(client, engineer_headers, product.id, name="Zertifikat für Müller.pdf").json()

    header = client.get(document["download_url"], headers=engineer_headers).headers[
        "content-disposition"
    ]

    assert "filename*=UTF-8''Zertifikat%20f%C3%BCr%20M%C3%BCller.pdf" in header
    assert header.isascii()  # headers must be plain ASCII


def test_downloading_requires_login(client, storage, engineer_headers, product):
    document = upload(client, engineer_headers, product.id).json()
    assert client.get(document["download_url"]).status_code == 401


def test_downloading_an_unknown_document_is_404(client, storage, readonly_headers):
    response = client.get(f"{DOCUMENTS}/9999/download", headers=readonly_headers)
    assert response.status_code == 404 and response.json()["code"] == "not_found"


def test_a_file_missing_from_storage_is_a_clear_404(client, storage, engineer_headers, product):
    """On the free Render tier the disk is wiped on deploy, while the database rows survive."""
    document = upload(client, engineer_headers, product.id).json()
    for path in stored_files(storage):
        path.unlink()

    response = client.get(document["download_url"], headers=engineer_headers)

    assert response.status_code == 404
    assert "no longer available" in response.json()["detail"]


# --- listing and deleting ---


def test_documents_are_listed_newest_first_in_pages(
    client, storage, engineer_headers, readonly_headers, product
):
    for name in ("one.pdf", "two.pdf", "three.pdf"):
        upload(client, engineer_headers, product.id, name=name)

    body = client.get(f"{DOCUMENTS}/product/{product.id}?limit=2", headers=readonly_headers).json()

    assert body["total"] == 3 and len(body["items"]) == 2
    assert [d["filename"] for d in body["items"]] == ["three.pdf", "two.pdf"]
    assert all("file_path" not in d for d in body["items"])


def test_listing_documents_of_an_unknown_product_is_404(client, readonly_headers):
    assert client.get(f"{DOCUMENTS}/product/9999", headers=readonly_headers).status_code == 404


def test_get_one_document(client, storage, engineer_headers, readonly_headers, product):
    document = upload(client, engineer_headers, product.id).json()

    assert (
        client.get(f"{DOCUMENTS}/{document['id']}", headers=readonly_headers).json()["id"]
        == document["id"]
    )


def test_only_admins_can_delete_and_the_file_is_removed(
    client, storage, engineer_headers, admin_headers, product, db_session
):
    document = upload(client, engineer_headers, product.id).json()

    assert (
        client.delete(f"{DOCUMENTS}/{document['id']}", headers=engineer_headers).status_code == 403
    )
    assert len(stored_files(storage)) == 1

    assert client.delete(f"{DOCUMENTS}/{document['id']}", headers=admin_headers).status_code == 204
    assert stored_files(storage) == []
    assert db_session.query(Document).count() == 0


def test_deleting_a_product_removes_its_files_too(
    client, storage, engineer_headers, admin_headers, product
):
    upload(client, engineer_headers, product.id, name="a.pdf")
    upload(client, engineer_headers, product.id, name="b.pdf")
    assert len(stored_files(storage)) == 2

    assert client.delete(f"/api/v1/products/{product.id}", headers=admin_headers).status_code == 204

    assert stored_files(storage) == []


def test_deleting_a_standard_keeps_documents_and_unlinks_them(
    client, storage, engineer_headers, admin_headers, product, db_session
):
    standard = Standard(standard_number="UL 508", title="T", issuing_body="UL")
    db_session.add(standard)
    db_session.commit()
    upload(client, engineer_headers, product.id, standard_id=standard.id)

    response = client.delete(f"/api/v1/standards/{standard.id}", headers=admin_headers)

    assert response.status_code == 204  # used to fail on the foreign key
    document = db_session.query(Document).one()
    assert document.standard_id is None
    assert len(stored_files(storage)) == 1


# --- the storage layer itself ---


def test_storage_refuses_keys_that_escape_its_folder(tmp_path):
    local = LocalStorage(tmp_path / "uploads")

    for key in ("../outside.txt", "../../etc/passwd", "/etc/passwd"):
        with pytest.raises(ValueError):
            local.save(key, io.BytesIO(b"data"), 1024)
        local.delete(key)  # silently ignored, and nothing outside is touched

    assert not (tmp_path / "outside.txt").exists()


def test_storage_finds_documents_stored_by_the_earlier_version(tmp_path, monkeypatch):
    """Older rows stored 'uploads/<name>' relative to the working directory."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "uploads").mkdir()
    (tmp_path / "uploads" / "old-file.pdf").write_bytes(PDF)
    local = LocalStorage("uploads")

    with local.open("uploads/old-file.pdf") as handle:
        assert handle.read() == PDF
    local.delete("uploads/old-file.pdf")
    assert not (tmp_path / "uploads" / "old-file.pdf").exists()


def test_deleting_a_missing_file_is_not_an_error(tmp_path):
    LocalStorage(tmp_path).delete("never-existed.pdf")
