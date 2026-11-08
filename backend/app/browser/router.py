import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.access import policy as access
from app.access.deps import CurrentUser, require
from app.browser import manager
from app.configuration import imports
from app.configuration.router import _run_import
from app.core.entities import Company
from app.core.events.bus import EventBus
from app.core.i18n import tx
from app.core.tenancy import current_company
from app.database import get_db
from app.dependencies import get_event_bus

router = APIRouter(prefix="/browser", tags=["browser"])


class TaskIn(BaseModel):
    goal: str = Field(min_length=5, max_length=1500)
    start_url: str | None = Field(default=None, max_length=500)


class InputIn(BaseModel):
    type: str = Field(pattern="^(click|type|key|scroll)$")
    x: float | None = None
    y: float | None = None
    text: str | None = Field(default=None, max_length=500)
    key: str | None = Field(default=None, max_length=30)
    direction: str | None = None


def _task(company: Company, task_id: str) -> manager.Task:
    task = manager.get(company.id, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=tx("Tâche introuvable (elle a pu s'arrêter).", "Task not found."))
    return task


@router.get("/status")
def status(company: Company = Depends(current_company), _u: CurrentUser = Depends(require(access.WRITE_SETTINGS))) -> dict:
    current = next((t for t in manager.TASKS.values() if t.company_id == company.id and t.status in manager.ACTIVE), None)
    return {"available": manager.available(), "provider": manager.provider(), "active": current.public() if current else None}


@router.post("/tasks", status_code=201)
def start(payload: TaskIn, company: Company = Depends(current_company), _u: CurrentUser = Depends(require(access.WRITE_SETTINGS))) -> dict:
    if not manager.available():
        raise HTTPException(status_code=400, detail=tx("Le navigateur de l'IA n'est pas configuré (clé du navigateur cloud et clé OpenRouter).", "The AI browser is not configured."))
    try:
        return manager.start(company.id, payload.goal, payload.start_url).public()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/tasks/{task_id}")
def read(task_id: str, company: Company = Depends(current_company), _u: CurrentUser = Depends(require(access.WRITE_SETTINGS))) -> dict:
    return _task(company, task_id).public()


@router.get("/tasks/{task_id}/screen")
def screen(task_id: str, company: Company = Depends(current_company), _u: CurrentUser = Depends(require(access.WRITE_SETTINGS))) -> Response:
    task = _task(company, task_id)
    if task.shot is None:
        raise HTTPException(status_code=404, detail="no screen yet")
    return Response(content=task.shot, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.post("/tasks/{task_id}/take-over")
def take_over(task_id: str, company: Company = Depends(current_company), _u: CurrentUser = Depends(require(access.WRITE_SETTINGS))) -> dict:
    task = _task(company, task_id)
    manager.take_over(task)
    return task.public()


@router.post("/tasks/{task_id}/hand-back")
def hand_back(task_id: str, company: Company = Depends(current_company), _u: CurrentUser = Depends(require(access.WRITE_SETTINGS))) -> dict:
    task = _task(company, task_id)
    manager.hand_back(task)
    return task.public()


@router.post("/tasks/{task_id}/cancel")
def cancel(task_id: str, company: Company = Depends(current_company), _u: CurrentUser = Depends(require(access.WRITE_SETTINGS))) -> dict:
    task = _task(company, task_id)
    manager.cancel(task)
    return task.public()


@router.post("/tasks/{task_id}/input")
def send_input(task_id: str, payload: InputIn, company: Company = Depends(current_company), _u: CurrentUser = Depends(require(access.WRITE_SETTINGS))) -> dict:
    """What the person does while in control. Typed text goes straight to the page."""

    task = _task(company, task_id)
    if task.status not in ("human", "needs_human"):
        raise HTTPException(status_code=409, detail=tx("Prenez d'abord la main.", "Take control first."))
    if payload.type == "click" and (payload.x is None or payload.y is None):
        raise HTTPException(status_code=422, detail="x and y required")
    task.inbox.put(payload.model_dump())
    return {"ok": True}


@router.post("/tasks/{task_id}/downloads/{index}/import")
async def import_download(
    task_id: str, index: int, company: Company = Depends(current_company), db: Session = Depends(get_db),
    event_bus: EventBus = Depends(get_event_bus), _u: CurrentUser = Depends(require(access.WRITE_SETTINGS)),
) -> dict:
    """A file the AI exported for the company goes through the same import as a dropped file."""

    task = _task(company, task_id)
    if index < 0 or index >= len(task.downloads):
        raise HTTPException(status_code=404, detail=tx("Fichier introuvable.", "File not found."))
    item = task.downloads[index]
    try:
        kind = imports.detect_kind(item["name"], item["content"])
    except imports.ImportError_ as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return await _run_import(db, company, kind, item["name"], item["content"], None, event_bus)
