from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import require_user
from app.db.database import get_db
from app.schemas.dashboard import DashboardSummary
from app.services import dashboard as dashboard_service

router = APIRouter(
    prefix="/api/v1/dashboard",
    tags=["Dashboard"],
    dependencies=[Depends(require_user)],
)


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    limit: int = Query(10, ge=1, le=50, description="How many expiring / expired records to list"),
    db: Session = Depends(get_db),
):
    return dashboard_service.build_summary(db, limit=limit)
