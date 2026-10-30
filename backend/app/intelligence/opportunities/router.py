import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.entities import Opportunity
from app.database import get_db
from app.intelligence.opportunities.schemas import OpportunityRead

router = APIRouter(prefix="/intelligence/opportunities", tags=["intelligence"])


@router.get("", response_model=list[OpportunityRead])
def list_opportunities(db: Session = Depends(get_db)) -> list[Opportunity]:
    return list(db.query(Opportunity).order_by(Opportunity.created_at.desc()).all())


@router.get("/{opportunity_id}", response_model=OpportunityRead)
def get_opportunity(opportunity_id: uuid.UUID, db: Session = Depends(get_db)) -> Opportunity:
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None:
        raise HTTPException(status_code=404, detail=f"Opportunity {opportunity_id} not found")
    return opportunity
