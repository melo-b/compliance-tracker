from datetime import date

from pydantic import BaseModel, Field

from app.schemas.standard import ProductComplianceResponse


class DashboardTotals(BaseModel):
    products: int
    standards: int
    compliance_records: int


class DashboardSummary(BaseModel):
    """Everything the dashboard page needs, in one request."""

    as_of: date = Field(description="The date (UTC) the figures were calculated for")
    expiring_soon_days: int = Field(description="The 'Expiring Soon' window in days")
    totals: DashboardTotals
    by_workflow: dict[str, int] = Field(description="Records per workflow status")
    by_validity: dict[str, int] = Field(
        description="Final records per validity. Pending and Draft records have none"
    )
    expiring_soon: list[ProductComplianceResponse] = Field(
        description="The soonest-to-expire certificates that have not yet expired"
    )
    expired: list[ProductComplianceResponse] = Field(
        description="The most recently expired certificates"
    )
