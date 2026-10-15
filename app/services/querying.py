"""Shared helpers for list endpoints: sorting and pagination."""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import InvalidRequestError
from app.schemas.pagination import PageParams


def apply_sorting(
    statement: Select,
    sort: str | None,
    allowed: Mapping[str, ColumnElement[Any]],
    default: str,
    tiebreaker: ColumnElement[Any] | None = None,
) -> Select:
    """Orders `statement` by a comma-separated `sort` such as "-expiration_date,name".

    A leading "-" means descending. Only the whitelisted fields in `allowed` are accepted, so
    callers can never sort by (or probe) an arbitrary column. NULLs always sort last. The
    tiebreaker (the primary key by default) makes the order, and therefore paging, deterministic.
    """
    keys = [part.strip() for part in (sort or default).split(",") if part.strip()]
    if not keys:
        keys = [default]

    clauses = []
    for key in keys:
        descending = key.startswith("-")
        name = key.lstrip("-+")
        if name not in allowed:
            raise InvalidRequestError(
                f"Cannot sort by '{name}'. Allowed fields: {', '.join(sorted(allowed))}"
            )
        column = allowed[name]
        clauses.append((column.desc() if descending else column.asc()).nulls_last())

    clauses.append((tiebreaker if tiebreaker is not None else allowed["id"]).asc())
    return statement.order_by(*clauses)


def paginate(db: Session, statement: Select, page: PageParams) -> tuple[list, int]:
    """Returns (the requested slice of rows, the total number of matching rows)."""
    total = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery()))
    rows = db.scalars(statement.offset(page.skip).limit(page.limit)).all()
    return list(rows), total or 0


def contains(column: ColumnElement[str], text: str) -> ColumnElement[bool]:
    """Case-insensitive "contains" match that treats % and _ in the text literally."""
    escape = "\\"
    escaped = text.replace(escape, escape * 2).replace("%", escape + "%").replace("_", escape + "_")
    return column.ilike(f"%{escaped}%", escape=escape)
