from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field


class DocumentResponse(BaseModel):
    """A stored document. The internal storage key is deliberately never exposed."""

    id: int
    filename: str = Field(description="The sanitised original file name")
    product_id: int
    standard_id: int | None = None
    upload_date: datetime | None = None
    content_type: str | None = None
    size_bytes: int | None = None

    model_config = ConfigDict(from_attributes=True)

    @computed_field(description="Where to download the file (requires login)")
    @property
    def download_url(self) -> str:
        return f"/api/v1/documents/{self.id}/download"
