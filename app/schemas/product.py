from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class ProductBase(BaseModel):
    name: Text = Field(..., description="The commercial name of the product or component")
    model_number: Text = Field(
        ..., description="The unique manufacturer model number used for physical tracking"
    )
    description: str | None = Field(
        None, max_length=2000, description="Detailed description of the component and its function"
    )


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    """Partial update: only the fields that are sent are changed."""

    name: Text | None = None
    model_number: Text | None = None
    description: str | None = Field(None, max_length=2000)


class ProductResponse(ProductBase):
    id: int

    # Read the data directly from the SQLAlchemy ORM model
    model_config = ConfigDict(from_attributes=True)


class ProductSummary(BaseModel):
    """The few product fields shown next to a compliance record."""

    id: int
    name: str
    model_number: str

    model_config = ConfigDict(from_attributes=True)
