from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db 
from app.models.product import Product
from app.schemas.product import ProductResponse, ProductCreate

router = APIRouter(prefix="/api/v1/products", tags=["Products"])

# 1. Create a Product (POST)
@router.post("/", response_model=ProductResponse, status_code=201)
def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    # Check for existing model number to prevent database integrity errors
    db_product = db.query(Product).filter(Product.model_number == product.model_number).first()
    if db_product:
        raise HTTPException(status_code=400, detail="Model number already registered")
        
    new_product = Product(**product.model_dump())
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product

# 2. Get All Products (GET)
@router.get("/", response_model=List[ProductResponse])
def get_products(db: Session = Depends(get_db), skip: int = 0, limit: int = 100):
    products = db.query(Product).offset(skip).limit(limit).all()
    return products

# 3. Get a Specific Product by ID (GET)
@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
        
    return product