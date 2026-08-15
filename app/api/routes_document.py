from app.models.user import User
from app.api.dependencies import get_current_user

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.document import Document
from app.models.product import Product
from app.models.standard import Standard
from app.schemas.document import DocumentResponse
from app.services.file_handler import save_upload_file

router = APIRouter(prefix="/api/v1/documents", tags=["Documents"])

# 1. Upload a Document
@router.post("/upload/", response_model=DocumentResponse, status_code=201)
def upload_document(
    product_id: int = Form(...), 
    standard_id: Optional[int] = Form(None),
    file: UploadFile = File(...), 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify the product actually exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # If a standard_id was provided, verify it exists too
    if standard_id:
        standard = db.query(Standard).filter(Standard.id == standard_id).first()
        if not standard:
            raise HTTPException(status_code=404, detail="Standard not found")

    # Pass the file to our service handler to save to disk
    saved_file_path = save_upload_file(file)

    # Create the database record with all the metadata
    new_document = Document(
        filename=file.filename,
        file_path=saved_file_path,
        product_id=product_id,
        standard_id=standard_id  # Save it to the database
    )
    
    db.add(new_document)
    db.commit()
    db.refresh(new_document)
    
    return new_document

# 2. Get Documents by Product ID
@router.get("/product/{product_id}", response_model=List[DocumentResponse])
def get_product_documents(product_id: int, db: Session = Depends(get_db)):
    documents = db.query(Document).filter(Document.product_id == product_id).all()
    return documents