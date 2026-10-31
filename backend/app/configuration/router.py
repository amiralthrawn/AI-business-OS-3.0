from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.access.deps import CurrentUser, require
from app.access import policy as access
from app.configuration import imports, sectors, service, tools
from app.core.entities import Company
from app.core.i18n import tx
from app.database import get_db

router = APIRouter(prefix="/configuration", tags=["configuration"])


class ConfigurationUpdate(BaseModel):
    sector_key: str | None = None
    sector_custom: str | None = Field(default=None, max_length=200)
    functions: list[str] | None = None
    tools: list[str] | None = None
    custom_tools: list[str] | None = None
    problems: str | None = Field(default=None, max_length=4000)
    external_factors: str | None = Field(default=None, max_length=4000)
    company_size: str | None = None
    country: str | None = None
    business_model: str | None = Field(default=None, max_length=120)
    objectives: str | None = Field(default=None, max_length=4000)
    answers: dict[str, list[str]] | None = None
    answer_notes: dict[str, str] | None = None


def _company(db: Session) -> Company:
    company = db.query(Company).first()
    if company is None:
        raise HTTPException(status_code=404, detail=tx("Aucune entreprise n'est encore configurée", "No company is configured yet"))
    return company


@router.get("/catalog")
def get_catalog() -> dict:
    return {
        "sectors": [{"key": k, "label": label, "group": g, "group_label": sectors.GROUPS[g].label} for k, label, g in sectors.SECTORS],
        "groups": [
            {
                "key": g.key,
                "label": g.label,
                "business_models": list(g.business_models),
                "questions": list(g.questions),
                "qcm": [{"key": key, "title": sectors.QCM_TITLES[key][0], "hint": sectors.QCM_TITLES[key][1], "choices": list(choices)} for key, choices in sectors.qcm_for(g.key).items()],
            }
            for g in sectors.GROUPS.values()
        ],
        "tool_pages": [{"key": k, "title": t, "why": w, "categories": list(c)} for k, t, w, c in tools.TOOL_PAGES],
        "functions": [{"key": k, "label": label, "description": d} for k, label, d in sectors.FUNCTIONS],
        "categories": [{"key": c.key, "label": c.label, "data": list(c.data), "ai_use": c.ai_use} for c in tools.CATEGORIES.values()],
        "tools": [{"key": k, "label": label, "category": c} for k, label, c in tools.TOOLS],
    }


@router.get("")
def get_configuration(db: Session = Depends(get_db)) -> dict:
    company = _company(db)
    config = service.get_configuration(db, company.id)
    return {"configuration": config, "ai_profile": service.ai_profile(config), "configured": bool(config.get("completed_at"))}


@router.put("")
def put_configuration(payload: ConfigurationUpdate, db: Session = Depends(get_db), _user: CurrentUser = Depends(require(access.WRITE_SETTINGS))) -> dict:
    company = _company(db)
    context = service.save_configuration(
        db,
        company,
        sector_key=payload.sector_key,
        sector_custom=payload.sector_custom,
        functions=payload.functions,
        tool_keys=payload.tools,
        custom_tools=payload.custom_tools,
        problems=payload.problems,
        external_factors=payload.external_factors,
        company_size=payload.company_size,
        country=payload.country,
        business_model=payload.business_model,
        objectives=payload.objectives,
        answers=payload.answers,
        answer_notes=payload.answer_notes,
    )
    config = dict(context.configuration or {})
    return {"configuration": config, "ai_profile": service.ai_profile(config), "configured": bool(config.get("completed_at"))}


@router.get("/integration-plan")
def get_integration_plan(db: Session = Depends(get_db)) -> dict:
    company = _company(db)
    config = service.get_configuration(db, company.id)
    return {"tools": service.integration_plan(config), "custom_tools": config.get("custom_tools") or [], "imports": config.get("imports") or [], "fec_summary": config.get("fec_summary")}


@router.post("/imports/auto")
async def import_auto(
    file: UploadFile = File(...),
    tool: str | None = None,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require(access.WRITE_SETTINGS)),
) -> dict:
    """One drop zone for every file: the kind (FEC, customers, suppliers,
    products) is recognised from the file itself."""

    company = _company(db)
    content = await file.read(imports.MAX_BYTES + 1)
    try:
        kind = imports.detect_kind(file.filename or "", content)
    except imports.ImportError_ as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return await _run_import(db, company, kind, file.filename or "", content, tool)


@router.post("/tools/{tool_key}/request-connection")
def request_tool_connection(tool_key: str, db: Session = Depends(get_db), _user: CurrentUser = Depends(require(access.WRITE_SETTINGS))) -> dict:
    company = _company(db)
    try:
        return service.request_connection(db, company.id, tool_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=tx("Cet outil n'est pas dans votre liste.", "This tool is not in your list.")) from exc


@router.post("/imports/{kind}")
async def import_file(
    kind: str,
    file: UploadFile = File(...),
    tool: str | None = None,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require(access.WRITE_SETTINGS)),
) -> dict:
    if kind not in ("customers", "suppliers", "products", "fec"):
        raise HTTPException(status_code=404, detail=tx("Type d'import inconnu", "Unknown import type"))
    company = _company(db)
    content = await file.read(imports.MAX_BYTES + 1)
    return await _run_import(db, company, kind, file.filename or "", content, tool)


async def _run_import(db: Session, company: Company, kind: str, filename: str, content: bytes, tool: str | None) -> dict:
    try:
        if kind == "fec":
            result, summary = imports.import_fec(db, company.id, content)
        else:
            summary = None
            result = imports.import_entities(db, company.id, kind, imports.read_table(filename, content))
    except imports.ImportError_ as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    entry = {"kind": kind, "file": filename[:200], "created": result.created, "updated": result.updated, "skipped": result.skipped, "tool": tool}
    if summary:
        entry["summary"] = summary
    db.commit()
    service.record_import(db, company.id, tool, entry)
    return {
        "kind": kind,
        "rows": result.rows,
        "created": result.created,
        "updated": result.updated,
        "skipped": result.skipped,
        "problems": result.problems,
        "recognised_columns": result.recognised_columns,
        "summary": summary,
    }
