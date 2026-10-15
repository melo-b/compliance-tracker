from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models.document import Document
from app.models.standard import Standard, StandardStatus
from app.schemas.pagination import PageParams
from app.schemas.standard import StandardCreate, StandardUpdate
from app.services.querying import apply_sorting, contains, paginate

SORTABLE = {
    "id": Standard.id,
    "standard_number": Standard.standard_number,
    "title": Standard.title,
    "issuing_body": Standard.issuing_body,
    "status": Standard.status,
    "publication_date": Standard.publication_date,
    "effective_date": Standard.effective_date,
}

NUMBER_TAKEN = "Standard number already registered"


def list_standards(
    db: Session,
    page: PageParams,
    sort: str | None,
    q: str | None,
    status: StandardStatus | None,
    issuing_body: str | None,
) -> tuple[list[Standard], int]:
    statement = select(Standard)
    if q:
        statement = statement.where(
            contains(Standard.standard_number, q) | contains(Standard.title, q)
        )
    if status:
        statement = statement.where(Standard.status == status)
    if issuing_body:
        statement = statement.where(contains(Standard.issuing_body, issuing_body))
    statement = apply_sorting(statement, sort, SORTABLE, default="standard_number")
    return paginate(db, statement, page)


def get_standard(db: Session, standard_id: int) -> Standard:
    standard = db.get(Standard, standard_id)
    if standard is None:
        raise NotFoundError("Standard not found")
    return standard


def _number_in_use(db: Session, number: str, exclude_id: int | None = None) -> bool:
    statement = select(Standard.id).where(Standard.standard_number == number)
    if exclude_id is not None:
        statement = statement.where(Standard.id != exclude_id)
    return db.scalar(statement) is not None


def create_standard(db: Session, data: StandardCreate) -> Standard:
    if _number_in_use(db, data.standard_number):
        raise ConflictError(NUMBER_TAKEN)

    standard = Standard(**data.model_dump())
    db.add(standard)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(NUMBER_TAKEN) from None
    db.refresh(standard)
    return standard


def update_standard(db: Session, standard_id: int, data: StandardUpdate) -> Standard:
    standard = get_standard(db, standard_id)
    changes = data.model_dump(exclude_unset=True)

    for required in ("standard_number", "title", "issuing_body", "status"):
        if required in changes and changes[required] is None:
            del changes[required]

    if "standard_number" in changes and _number_in_use(
        db, changes["standard_number"], exclude_id=standard_id
    ):
        raise ConflictError("Standard number already registered to another entry")

    for key, value in changes.items():
        setattr(standard, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(NUMBER_TAKEN) from None
    db.refresh(standard)
    return standard


def delete_standard(db: Session, standard_id: int) -> None:
    """Deletes the standard and its compliance records.

    Documents belong to a product, so any that referenced the standard are kept and simply
    lose the (optional) link, instead of the delete failing on the foreign key.
    """
    standard = get_standard(db, standard_id)
    db.execute(update(Document).where(Document.standard_id == standard_id).values(standard_id=None))
    db.delete(standard)
    db.commit()
