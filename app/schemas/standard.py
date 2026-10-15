from datetime import date
from typing import Annotated, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    computed_field,
    model_validator,
)

from app.models.standard import StandardStatus, WorkflowStatus
from app.services.compliance_logic import Validity, compute_validity, days_until_expiry


# ==========================================
# 1. REGULATORY STANDARD SCHEMAS
# Represents the actual standards (e.g., UL, CSA, IEC)
# ==========================================

class StandardBase(BaseModel):
    standard_number: str = Field(..., description="The official alphanumeric designation (e.g., UL 508, CSA C22.2 No. 14)")
    title: str = Field(..., description="The formal title of the regulatory standard")
    publication_date: Optional[date] = Field(None, description="Date the standard was published")
    effective_date: Optional[date] = Field(None, description="Date the standard goes into effect")
    issuing_body: str = Field(..., description="The organization issuing the standard (e.g., CSA, UL, CE)")
    status: StandardStatus = Field(default=StandardStatus.ACTIVE, description="Current lifecycle status of the standard")

class StandardCreate(StandardBase):
    pass

class StandardUpdate(BaseModel):
    standard_number: Optional[str] = None
    title: Optional[str] = None
    publication_date: Optional[date] = None
    effective_date: Optional[date] = None
    issuing_body: Optional[str] = None
    status: Optional[StandardStatus] = None

class StandardResponse(StandardBase):
    id: int
    
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 2. PRODUCT COMPLIANCE (ASSOCIATION) SCHEMAS
# Maps a specific product to a standard and tracks the certification workflow
# (Pending -> Draft -> Final) and, once final, the certificate's expiry.
# ==========================================

TrimmedText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]


class ProductComplianceBase(BaseModel):
    certificate_number: TrimmedText | None = Field(
        None, description="The certificate number issued by the agency"
    )
    agency: TrimmedText | None = Field(
        None, description="The certification agency (e.g., CSA Group, UL)"
    )
    issued_date: date | None = Field(None, description="The date the certificate was issued")
    expiration_date: date | None = Field(
        None, description="The date the certificate expires. Leave empty if it does not expire"
    )


class _DatesInOrder(BaseModel):
    @model_validator(mode="after")
    def _expiry_not_before_issue(self):
        issued, expires = self.issued_date, self.expiration_date
        if issued is not None and expires is not None and expires < issued:
            raise ValueError("expiration_date cannot be before issued_date")
        return self


class ProductComplianceCreate(ProductComplianceBase, _DatesInOrder):
    """New records always start as Pending; use the transition endpoint to move them on."""

    model_config = ConfigDict(extra="forbid")

    product_id: int = Field(..., description="The ID of the manufactured product")
    standard_id: int = Field(..., description="The ID of the regulatory standard")


class ProductComplianceUpdate(ProductComplianceBase, _DatesInOrder):
    """Edits certificate details. The workflow status cannot be changed here."""

    model_config = ConfigDict(extra="forbid")


class WorkflowTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: WorkflowStatus = Field(..., description="The status to move the record to")


class ProductComplianceResponse(ProductComplianceBase):
    id: int
    product_id: int
    standard_id: int
    workflow_status: WorkflowStatus

    model_config = ConfigDict(from_attributes=True)

    @computed_field(description="Valid / Expiring Soon / Expired. Only present once Final")
    @property
    def validity(self) -> Validity | None:
        return compute_validity(self.workflow_status, self.expiration_date)

    @computed_field(description="Days until expiry (negative once expired); null if none")
    @property
    def days_until_expiry(self) -> int | None:
        return days_until_expiry(self.expiration_date)
