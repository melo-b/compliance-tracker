from dataclasses import dataclass
from typing import Any

from fastapi import Query
from pydantic import BaseModel, Field

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class Page[T](BaseModel):
    """Envelope for every list endpoint."""

    items: list[T]
    total: int = Field(description="Number of items matching the filters, across all pages")
    skip: int
    limit: int


@dataclass(frozen=True)
class PageParams:
    skip: int
    limit: int


def pagination(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Maximum items to return"),
) -> PageParams:
    return PageParams(skip=skip, limit=limit)


def make_page(items: list[Any], total: int, page: PageParams) -> dict[str, Any]:
    """The value a list route returns; FastAPI validates it against Page[...]."""
    return {"items": items, "total": total, "skip": page.skip, "limit": page.limit}
