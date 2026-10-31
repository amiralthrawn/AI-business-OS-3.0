from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.access.deps import CurrentUser, get_current_user
from app.core.entities import Company
from app.database import get_db
from app.home.schemas import CompanyNarrativeItemRead, HomeResponse, OSActivityRead
from app.home.scoping import domain_visible, scope_home, scope_tasks, viewer_and_briefing
from app.home.service import HomeService

router = APIRouter(prefix="/home", tags=["home"])


def _the_company(db: Session) -> Company | None:
    return db.query(Company).first()


@router.get("", response_model=HomeResponse)
def get_command_center(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)) -> dict:
    """Home IS the Command Center (see brain/home_command_center.md): this
    single endpoint is the structured read model the brief's own
    `GET /home/command-center` example asked for, adapted to reuse the
    endpoint that already served this purpose since step 8 rather than
    standing up a second, parallel one."""

    company = _the_company(db)
    company_id = company.id if company is not None else None
    scoped = scope_home(HomeService(db).get_command_center(company_id), user)
    scoped["tasks"] = scope_tasks(db, user)
    return {**scoped, **viewer_and_briefing(db, company_id, scoped, user)}


@router.get("/activity", response_model=list[OSActivityRead])
def get_os_activity(domain: str | None = None, limit: int = 30, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)) -> list[dict]:
    """The full, filterable "Activité de l'OS" feed (Step 27) -- the same
    translation `GET /home`'s own short preview uses, just not capped to 6."""

    items = HomeService(db).get_os_activity(limit=limit, domain=domain)
    return [a for a in items if a["domain"] is None and user.can("view:intelligence") or a["domain"] is not None and domain_visible(user, a["domain"])]


@router.get("/narrative", response_model=list[CompanyNarrativeItemRead])
def get_company_narrative(limit: int = 30, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)) -> list[dict]:
    """The full "vie de l'entreprise" feed (Step 27) -- real Communications,
    not capped to `GET /home`'s own 6-item preview."""

    company = _the_company(db)
    if company is None or not user.can("view:communications"):
        return []
    return HomeService(db).get_company_narrative(company.id, limit=limit)
