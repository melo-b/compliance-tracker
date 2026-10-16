from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin, require_engineer, require_user
from app.db.database import get_db
from app.schemas.pagination import Page, PageParams, make_page, pagination
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate
from app.services import products as product_service
from app.services.storage import Storage, get_storage

# Every route requires a logged-in user; writes additionally require a role (see README).
router = APIRouter(
    prefix="/api/v1/products",
    tags=["Products"],
    dependencies=[Depends(require_user)],
)


@router.post(
    "/",
    response_model=ProductResponse,
    status_code=201,
    dependencies=[Depends(require_engineer)],
)
def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    return product_service.create_product(db, product)


@router.get("/", response_model=Page[ProductResponse])
def list_products(
    page: PageParams = Depends(pagination),
    sort: str | None = Query(None, description="Comma-separated fields; prefix - for descending"),
    q: str | None = Query(None, description="Matches part of the name or model number"),
    db: Session = Depends(get_db),
):
    items, total = product_service.list_products(db, page, sort, q)
    return make_page(items, total, page)


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db)):
    return product_service.get_product(db, product_id)


@router.patch(
    "/{product_id}", response_model=ProductResponse, dependencies=[Depends(require_engineer)]
)
def update_product(product_id: int, product_update: ProductUpdate, db: Session = Depends(get_db)):
    return product_service.update_product(db, product_id, product_update)


@router.delete("/{product_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_product(
    product_id: int, db: Session = Depends(get_db), storage: Storage = Depends(get_storage)
):
    product_service.delete_product(db, storage, product_id)
