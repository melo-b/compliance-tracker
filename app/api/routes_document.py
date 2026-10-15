from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin, require_engineer, require_user
from app.db.database import get_db
from app.schemas.document import DocumentResponse
from app.schemas.pagination import Page, PageParams, make_page, pagination
from app.services import documents as document_service
from app.services.storage import CHUNK_SIZE, Storage, get_storage

# Every route requires a logged-in user; uploading additionally requires an engineer or admin
# and deleting requires an admin.
router = APIRouter(
    prefix="/api/v1/documents",
    tags=["Documents"],
    dependencies=[Depends(require_user)],
)


@router.post(
    "/upload/",
    response_model=DocumentResponse,
    status_code=201,
    dependencies=[Depends(require_engineer)],
)
def upload_document(
    product_id: int = Form(...),
    standard_id: int | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_storage),
):
    return document_service.upload_document(db, storage, file, product_id, standard_id)


@router.get("/product/{product_id}", response_model=Page[DocumentResponse])
def list_product_documents(
    product_id: int,
    page: PageParams = Depends(pagination),
    sort: str | None = Query(None, description="Comma-separated fields; prefix - for descending"),
    db: Session = Depends(get_db),
):
    items, total = document_service.list_documents(db, product_id, page, sort)
    return make_page(items, total, page)


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: int, db: Session = Depends(get_db)):
    return document_service.get_document(db, document_id)


@router.get("/{document_id}/download")
def download_document(
    document_id: int, db: Session = Depends(get_db), storage: Storage = Depends(get_storage)
):
    document, stream = document_service.open_document(db, storage, document_id)

    def chunks():
        with stream:
            while chunk := stream.read(CHUNK_SIZE):
                yield chunk

    headers = {
        # Always a download, never rendered inside this site, whatever the file is
        "Content-Disposition": document_service.attachment_header(document.filename),
        "X-Content-Type-Options": "nosniff",
    }
    if document.size_bytes is not None:
        headers["Content-Length"] = str(document.size_bytes)
    return StreamingResponse(
        chunks(), media_type=document_service.media_type_for(document), headers=headers
    )


@router.delete("/{document_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_document(
    document_id: int, db: Session = Depends(get_db), storage: Storage = Depends(get_storage)
):
    document_service.delete_document(db, storage, document_id)
