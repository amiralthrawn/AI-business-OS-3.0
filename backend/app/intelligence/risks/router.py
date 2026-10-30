import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.entities import Risk
from app.database import get_db
from app.intelligence.risks.schemas import RiskRead

router = APIRouter(prefix="/intelligence/risks", tags=["intelligence"])


@router.get("", response_model=list[RiskRead])
def list_risks(db: Session = Depends(get_db)) -> list[Risk]:
    return list(db.query(Risk).order_by(Risk.created_at.desc()).all())


@router.get("/{risk_id}", response_model=RiskRead)
def get_risk(risk_id: uuid.UUID, db: Session = Depends(get_db)) -> Risk:
    risk = db.get(Risk, risk_id)
    if risk is None:
        raise HTTPException(status_code=404, detail=f"Risk {risk_id} not found")
    return risk
