from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.entities import Company
from app.database import get_db
from app.domains.finance import service
from app.domains.finance.schemas import FinanceOverview

router = APIRouter(prefix="/finance", tags=["finance"])


@router.get("/overview", response_model=FinanceOverview)
def get_finance_overview(db: Session = Depends(get_db)) -> dict:
    company = db.query(Company).first()
    return service.get_finance_overview(db, company.id if company is not None else None)
