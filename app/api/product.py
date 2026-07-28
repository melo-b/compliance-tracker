from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

# Import your DB dependency, SQLAlchemy models, and Pydantic schemas
# Adjust these import paths based on your exact setup!
from app.db.database import get_db 
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductResponse

# Initialize the router
router = APIRouter(
    prefix="/products",
    tags=["Products"]
)

@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(product_in: ProductCreate, db: Session = Depends(get_db)):
    """
    Create a new product component in the compliance tracker.
    """
    # 1. Check if a product with this model number already exists
    existing_product = db.query(Product).filter(Product.model_number == product_in.model_number).first()
    if existing_product:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A product with this model number already exists."
        )
    
    # 2. Convert the Pydantic schema (product_in) to a SQLAlchemy model instance
    db_product = Product(**product_in.model_dump())
    
    # 3. Add to the database and commit the transaction
    db.add(db_product)
    db.commit()
    db.refresh(db_product) # Refreshes to get the auto-generated 'id'
    
    # 4. Return the database object (FastAPI automatically converts it to ProductResponse)
    return db_product

@router.get("/", response_model=List[ProductResponse])
def get_products(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Retrieve a list of all products, with optional pagination.
    """
    products = db.query(Product).offset(skip).limit(limit).all()
    return products