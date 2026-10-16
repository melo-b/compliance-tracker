"""Document uploads: validation, storage and metadata.

Uploaded files are untrusted input, so three things hold no matter what the client sends:
the stored name never contains any part of the client's file name (it is a random id), only a
small whitelist of file types is accepted and the file's first bytes must match the claimed
type, and downloads are always sent as attachments so an uploaded file can never run in the
browser as part of this site.
"""

import mimetypes
import re
import unicodedata
import uuid
from pathlib import PurePosixPath
from urllib.parse import quote

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    InvalidRequestError,
    NotFoundError,
    UnsupportedMediaError,
)
from app.models.document import Document
from app.models.product import Product
from app.models.standard import Standard
from app.schemas.pagination import PageParams
from app.services.querying import apply_sorting, paginate
from app.services.storage import Storage

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ZIP_SIGNATURE = b"PK\x03\x04"  # .docx and .xlsx are zip containers

# extension -> (content type, accepted leading bytes)
ALLOWED_TYPES: dict[str, tuple[str, bytes]] = {
    ".pdf": ("application/pdf", b"%PDF-"),
    ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
    ".jpg": ("image/jpeg", b"\xff\xd8\xff"),
    ".jpeg": ("image/jpeg", b"\xff\xd8\xff"),
    ".docx": (DOCX, ZIP_SIGNATURE),
    ".xlsx": (XLSX, ZIP_SIGNATURE),
}
MAX_FILENAME_LENGTH = 100

SORTABLE = {
    "id": Document.id,
    "filename": Document.filename,
    "upload_date": Document.upload_date,
    "size_bytes": Document.size_bytes,
}


def sanitize_filename(name: str | None) -> str:
    """A safe, human-readable version of a client-supplied file name.

    Drops any directory part (Windows or POSIX style), keeps letters, digits and a few harmless
    symbols, and limits the length. The result is only ever *displayed*; it is never used to
    build a path on disk.
    """
    base = PurePosixPath((name or "").replace("\\", "/")).name
    base = unicodedata.normalize("NFKC", base)
    base = re.sub(r"[^\w.\- ()]", "_", base)
    base = re.sub(r"\s+", " ", base).strip(" .")

    stem, dot, extension = base.rpartition(".")
    if dot and len(base) > MAX_FILENAME_LENGTH:
        stem = stem[: MAX_FILENAME_LENGTH - len(extension) - 1]
        base = f"{stem}.{extension}"
    return base[:MAX_FILENAME_LENGTH] or "document"


def _extension(filename: str) -> str:
    return PurePosixPath(filename).suffix.lower()


def validate_file_type(filename: str, head: bytes) -> str:
    """Returns the content type if the name and the file's first bytes agree, else raises."""
    extension = _extension(filename)
    if extension not in ALLOWED_TYPES:
        allowed = ", ".join(sorted(ALLOWED_TYPES))
        raise UnsupportedMediaError(
            f"File type '{extension or 'unknown'}' is not allowed. Use: {allowed}"
        )

    content_type, signature = ALLOWED_TYPES[extension]
    if not head.startswith(signature):
        raise UnsupportedMediaError(f"The file's contents do not match its {extension} extension")
    return content_type


def upload_document(
    db: Session,
    storage: Storage,
    upload: UploadFile,
    product_id: int,
    standard_id: int | None,
) -> Document:
    if db.get(Product, product_id) is None:
        raise NotFoundError("Product not found")
    if standard_id is not None and db.get(Standard, standard_id) is None:
        raise NotFoundError("Standard not found")

    filename = sanitize_filename(upload.filename)

    head = upload.file.read(16)
    upload.file.seek(0)
    if not head:
        raise InvalidRequestError("The uploaded file is empty")
    content_type = validate_file_type(filename, head)

    # The stored name is random: no part of the client's name reaches the file system
    key = f"{uuid.uuid4().hex}{_extension(filename)}"
    size = storage.save(key, upload.file, get_settings().max_upload_bytes)

    document = Document(
        filename=filename,
        file_path=key,
        content_type=content_type,
        size_bytes=size,
        product_id=product_id,
        standard_id=standard_id,
    )
    db.add(document)
    try:
        db.commit()
    except BaseException:
        db.rollback()
        storage.delete(key)  # do not leave an orphaned file behind a failed insert
        raise
    db.refresh(document)
    return document


def get_document(db: Session, document_id: int) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise NotFoundError("Document not found")
    return document


def list_documents(
    db: Session, product_id: int, page: PageParams, sort: str | None
) -> tuple[list[Document], int]:
    if db.get(Product, product_id) is None:
        raise NotFoundError("Product not found")
    statement = select(Document).where(Document.product_id == product_id)
    statement = apply_sorting(statement, sort, SORTABLE, default="-upload_date")
    return paginate(db, statement, page)


def open_document(db: Session, storage: Storage, document_id: int):
    """Returns (document, open file). Raises NotFoundError if the file is no longer stored."""
    document = get_document(db, document_id)
    try:
        return document, storage.open(document.file_path)
    except FileNotFoundError:
        raise NotFoundError(
            "The stored file is no longer available (the server's temporary storage was reset)"
        ) from None


def delete_document(db: Session, storage: Storage, document_id: int) -> None:
    document = get_document(db, document_id)
    key = document.file_path
    db.delete(document)
    db.commit()
    storage.delete(key)


def media_type_for(document: Document) -> str:
    if document.content_type:
        return document.content_type
    return mimetypes.guess_type(document.filename)[0] or "application/octet-stream"


def attachment_header(filename: str) -> str:
    """Content-Disposition value that downloads `filename`, with a safe ASCII fallback."""
    ascii_name = re.sub(r"[^A-Za-z0-9._ -]", "_", filename)
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
