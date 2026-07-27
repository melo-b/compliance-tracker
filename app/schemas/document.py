from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime

# 1. Base Schema
class DocumentBase(BaseModel):
    filename: str = Field(..., description="The original name of the uploaded compliance document")
    file_path: str = Field(..., description="The internal storage path or URI where the document is securely saved")
    product_id: int = Field(..., description="The ID of the product this document belongs to")
    standard_id: Optional[int] = Field(None, description="The ID of the regulatory standard this document addresses (optional)")

# 2. Create Schema
# For POST requests when uploading a new document record.
# Note: In a real endpoint, you would upload the file first, generate the file_path, 
# and then pass this schema to the database.
class DocumentCreate(DocumentBase):
    pass

# 3. Update Schema
# For PATCH requests, likely used if a file is renamed or moved.
class DocumentUpdate(BaseModel):
    filename: Optional[str] = None
    file_path: Optional[str] = None
    product_id: Optional[int] = None
    standard_id: Optional[int] = None

# 4. Response Schema
# Includes the auto-generated primary key and the upload timestamp.
class DocumentResponse(DocumentBase):
    id: int
    upload_date: datetime = Field(..., description="The timestamp when the document was uploaded")
    
    model_config = ConfigDict(from_attributes=True)