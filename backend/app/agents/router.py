import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.access import policy as access
from app.access.deps import CurrentUser, get_current_user, require
from app.agents import perplexity, service
from app.core.entities import AgentProposal, Company
from app.core.i18n import tx
from app.database import get_db

router = APIRouter(prefix="/agents", tags=["agents"])

LABELS = {
    "veilleur": ("Veilleur", "Cherche en continu sur le web tout ce qui peut compter pour l'entreprise (Perplexity)."),
    "analyste": ("Analyste", "Lit vos chiffres et vos échanges pour repérer risques et opportunités."),
}


class SettingsIn(BaseModel):
    enabled: bool = True
    autonomy: dict[str, str] = Field(default_factory=dict)


class TopicsIn(BaseModel):
    topics: list[str] = Field(default_factory=list, max_length=12)
    run: bool = False


class AnswerIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


def _company(db: Session) -> Company:
    company = db.query(Company).first()
    if company is None:
        raise HTTPException(status_code=404, detail=tx("Aucune entreprise", "No company"))
    return company


def _proposal(db: Session, proposal_id: uuid.UUID) -> AgentProposal:
    proposal = db.get(AgentProposal, proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail=tx("Proposition introuvable", "Proposal not found"))
    return proposal


def _read(p: AgentProposal) -> dict:
    return {
        "id": str(p.id), "agent": p.agent, "kind": p.kind, "category": p.category, "title": p.title, "summary": p.summary,
        "why": p.why, "sources": p.sources or [], "event_date": p.event_date.isoformat() if p.event_date else None,
        "action_type": p.action_type, "action_text": (p.action_payload or {}).get("text"), "status": p.status,
        "created_at": p.created_at.isoformat(), "answer": p.answer,
    }


@router.get("/overview")
def overview(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)) -> dict:
    company = _company(db)
    is_director = user.can(access.WRITE_SETTINGS)
    proposals = []
    if user.can(access.VIEW_INTELLIGENCE) or is_director:
        rows = db.query(AgentProposal).filter(AgentProposal.status.in_(("new", "auto_done"))).order_by(AgentProposal.created_at.desc()).limit(40).all()
        proposals = [_read(p) for p in rows]
    agents = []
    for key, (label, description) in LABELS.items():
        run = service.last_run(db, company.id, key)
        configured = perplexity.configured() if key == "veilleur" else True
        agents.append({
            "key": key, "label": label, "description": description, "configured": configured,
            "last_status": run.status if run else None, "last_message": run.message if run else None,
            "last_run_at": run.created_at.isoformat() if run else None,
        })
    return {
        "guide": service.guide(db, company) if is_director else None,
        "proposals": proposals,
        "agents": agents if is_director else [],
        "settings": service.get_settings(db, company.id) if is_director else None,
        "cadence_hours": service.cadence_hours(),
    }


@router.put("/settings")
def put_settings(payload: SettingsIn, db: Session = Depends(get_db), _user: CurrentUser = Depends(require(access.WRITE_SETTINGS))) -> dict:
    return service.save_settings(db, _company(db).id, payload.enabled, payload.autonomy)


@router.put("/watch-topics")
def put_watch_topics(payload: TopicsIn, db: Session = Depends(get_db), _user: CurrentUser = Depends(require(access.WRITE_SETTINGS))) -> dict:
    """The subjects the company wants followed (sites, competitors, trade
    fairs...). With run=true the Veilleur starts looking right away."""

    company = _company(db)
    topics = service.set_watch_topics(db, company.id, payload.topics)
    result = None
    if payload.run:
        run = service.run_veilleur(db, company)
        result = {"status": run.status, "found": run.found, "message": run.message}
    return {"topics": topics, "run": result}


@router.post("/{agent}/run")
def run_agent(agent: str, db: Session = Depends(get_db), _user: CurrentUser = Depends(require(access.WRITE_SETTINGS))) -> dict:
    company = _company(db)
    if agent == "veilleur":
        run = service.run_veilleur(db, company)
    elif agent == "analyste":
        run = service.run_analyste(db, company)
    else:
        raise HTTPException(status_code=404, detail=tx("Agent inconnu", "Unknown agent"))
    return {"status": run.status, "found": run.found, "message": run.message}


@router.post("/proposals/{proposal_id}/accept")
def accept(proposal_id: uuid.UUID, db: Session = Depends(get_db), user: CurrentUser = Depends(require(access.ACTION_APPROVE))) -> dict:
    proposal = _proposal(db, proposal_id)
    if proposal.status != "new":
        raise HTTPException(status_code=409, detail=tx("Déjà traité.", "Already handled."))
    service.execute(db, proposal, automatic=False)
    db.commit()
    return _read(proposal)


@router.post("/proposals/{proposal_id}/ignore")
def ignore(proposal_id: uuid.UUID, db: Session = Depends(get_db), _user: CurrentUser = Depends(require(access.ACTION_APPROVE))) -> dict:
    proposal = _proposal(db, proposal_id)
    if proposal.status == "new":
        proposal.status = "ignored"
        proposal.decided_at = service.now()
        db.commit()
    return _read(proposal)


@router.post("/proposals/{proposal_id}/undo")
def undo(proposal_id: uuid.UUID, db: Session = Depends(get_db), _user: CurrentUser = Depends(require(access.ACTION_APPROVE))) -> dict:
    proposal = _proposal(db, proposal_id)
    if proposal.status not in ("auto_done", "accepted"):
        raise HTTPException(status_code=409, detail=tx("Rien à annuler.", "Nothing to undo."))
    service.undo(db, proposal)
    db.commit()
    return _read(proposal)


@router.post("/proposals/{proposal_id}/answer")
def answer(proposal_id: uuid.UUID, payload: AnswerIn, db: Session = Depends(get_db), _user: CurrentUser = Depends(require(access.WRITE_SETTINGS))) -> dict:
    proposal = _proposal(db, proposal_id)
    if proposal.kind != "missing_info":
        raise HTTPException(status_code=409, detail=tx("Cette proposition n'attend pas de réponse.", "This proposal expects no answer."))
    service.answer(db, proposal, payload.text)
    db.commit()
    return _read(proposal)
