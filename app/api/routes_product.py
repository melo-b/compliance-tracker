from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db 
from app.models.product import Product
from app.schemas.product import ProductResponse, ProductCreate, ProductUpdate

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

# 4. Update a Product (PATCH)
@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(product_id: int, product_update: ProductUpdate, db: Session = Depends(get_db)):
    db_product = db.query(Product).filter(Product.id == product_id).first()
    
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
        
    # extract only the fields the user actually sent in the request
    update_data = product_update.model_dump(exclude_unset=True)
    
    # If updating the model_number, verify it doesn't conflict with an existing product
    if "model_number" in update_data:
        existing_product = db.query(Product).filter(Product.model_number == update_data["model_number"]).first()
        if existing_product and existing_product.id != product_id:
            raise HTTPException(status_code=400, detail="Model number already registered to another product")

    # Apply the updates to the database model
    for key, value in update_data.items():
        setattr(db_product, key, value)
        
    db.commit()
    db.refresh(db_product)
    return db_product

# 5. Delete a Product (DELETE)
@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: int, db: Session = Depends(get_db)):
    db_product = db.query(Product).filter(Product.id == product_id).first()
    
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
        
    db.delete(db_product)
    db.commit()
    return None