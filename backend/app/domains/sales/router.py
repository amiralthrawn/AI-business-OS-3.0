from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.entities import Company
from app.database import get_db
from app.domains.sales.schemas import SalesOverview
from app.domains.sales.service import get_sales_overview

router = APIRouter(prefix="/sales", tags=["sales"])


@router.get("/overview", response_model=SalesOverview)
def get_overview(db: Session = Depends(get_db)) -> dict:
    company = db.query(Company).first()
    return get_sales_overview(db, company.id if company is not None else None)
