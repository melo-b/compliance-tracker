from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models.document import Document
from app.models.product import Product
from app.schemas.pagination import PageParams
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.querying import apply_sorting, contains, paginate
from app.services.storage import Storage

SORTABLE = {
    "id": Product.id,
    "name": Product.name,
    "model_number": Product.model_number,
}

MODEL_NUMBER_TAKEN = "Model number already registered"


def list_products(
    db: Session, page: PageParams, sort: str | None, q: str | None
) -> tuple[list[Product], int]:
    statement = select(Product)
    if q:
        statement = statement.where(contains(Product.name, q) | contains(Product.model_number, q))
    statement = apply_sorting(statement, sort, SORTABLE, default="id")
    return paginate(db, statement, page)


def get_product(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise NotFoundError("Product not found")
    return product


def _model_number_in_use(db: Session, model_number: str, exclude_id: int | None = None) -> bool:
    statement = select(Product.id).where(Product.model_number == model_number)
    if exclude_id is not None:
        statement = statement.where(Product.id != exclude_id)
    return db.scalar(statement) is not None


def create_product(db: Session, data: ProductCreate) -> Product:
    if _model_number_in_use(db, data.model_number):
        raise ConflictError(MODEL_NUMBER_TAKEN)

    product = Product(**data.model_dump())
    db.add(product)
    try:
        db.commit()
    except IntegrityError:  # lost a race with a concurrent request; the database is the arbiter
        db.rollback()
        raise ConflictError(MODEL_NUMBER_TAKEN) from None
    db.refresh(product)
    return product


def update_product(db: Session, product_id: int, data: ProductUpdate) -> Product:
    product = get_product(db, product_id)
    changes = data.model_dump(exclude_unset=True)

    # An explicit null cannot clear a required field
    for required in ("name", "model_number"):
        if required in changes and changes[required] is None:
            del changes[required]

    if "model_number" in changes and _model_number_in_use(
        db, changes["model_number"], exclude_id=product_id
    ):
        raise ConflictError("Model number already registered to another product")

    for key, value in changes.items():
        setattr(product, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(MODEL_NUMBER_TAKEN) from None
    db.refresh(product)
    return product


def delete_product(db: Session, storage: Storage, product_id: int) -> None:
    """Deletes the product, its compliance records and its documents (rows and files)."""
    product = get_product(db, product_id)
    stored_files = list(
        db.scalars(select(Document.file_path).where(Document.product_id == product_id))
    )

    db.delete(product)
    db.commit()

    for key in stored_files:  # only after the rows are gone, so a failure leaves no dangling rows
        storage.delete(key)
