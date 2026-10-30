"""Reads and writes the company's configuration and turns it into what the
rest of the product uses: the AI's sector profile and the integration plan."""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.business_context.service import BusinessContextService
from app.configuration import sectors, tools
from app.core.entities import BusinessContext, Company

FUNCTION_KEYS = [key for key, _, _ in sectors.FUNCTIONS]


def get_configuration(session: Session, company_id: uuid.UUID) -> dict:
    context = BusinessContextService(session).get_or_create(company_id)
    return dict(context.configuration or {})


def save_configuration(
    session: Session,
    company: Company,
    *,
    sector_key: str | None,
    sector_custom: str | None,
    functions: list[str] | None,
    tool_keys: list[str] | None,
    custom_tools: list[str] | None,
    problems: str | None,
    external_factors: str | None,
    company_size: str | None,
    country: str | None,
    business_model: str | None,
    objectives: str | None,
) -> BusinessContext:
    context = BusinessContextService(session).get_or_create(company.id)
    config = dict(context.configuration or {})

    if sector_key is not None:
        config["sector_key"] = sector_key if sectors.is_known_sector(sector_key) else "autre"
    if sector_custom is not None:
        config["sector_custom"] = sector_custom.strip()[:200]
    if problems is not None:
        config["problems"] = problems.strip()
    if external_factors is not None:
        config["external_factors"] = external_factors.strip()
    if custom_tools is not None:
        config["custom_tools"] = [t.strip()[:80] for t in custom_tools if t.strip()][:40]
    if tool_keys is not None:
        previous = dict(config.get("tools") or {})
        config["tools"] = {key: previous.get(key, {}) for key in dict.fromkeys(tool_keys) if tools.is_known_tool(key)}
    config.setdefault("completed_at", datetime.now(timezone.utc).isoformat())

    # The sector shown everywhere in the product is the company's own words
    # when it chose "Autre", else the catalogue label.
    label = sectors.sector_label(config.get("sector_key"))
    if config.get("sector_key") == "autre" and config.get("sector_custom"):
        label = config["sector_custom"]
    if label:
        company.industry = label[:255]
        session.add(company)

    if functions is not None:
        context.monitored_domains = [f for f in dict.fromkeys(functions) if f in FUNCTION_KEYS]
    if company_size is not None:
        context.company_size = company_size
    if country is not None:
        context.country = country
    if business_model is not None:
        context.business_model = business_model[:120]
    if objectives is not None:
        context.stated_objectives = objectives.strip() or None

    context.configuration = config
    session.add(context)
    session.commit()
    return context


def record_import(session: Session, company_id: uuid.UUID, tool_key: str | None, entry: dict) -> None:
    context = BusinessContextService(session).get_or_create(company_id)
    config = dict(context.configuration or {})
    entry = {**entry, "at": datetime.now(timezone.utc).isoformat()}
    config["imports"] = [*(config.get("imports") or []), entry][-50:]
    if tool_key and tools.is_known_tool(tool_key):
        configured = dict(config.get("tools") or {})
        state = dict(configured.get(tool_key) or {})
        state["data"] = "imported"
        state["last_import_at"] = entry["at"]
        configured[tool_key] = state
        config["tools"] = configured
    if entry.get("summary"):
        config["fec_summary"] = entry["summary"]
    context.configuration = config
    session.add(context)
    session.commit()


def ai_profile(config: dict) -> dict:
    """What the AI knows about this business before reading any data."""

    group = sectors.sector_group(config.get("sector_key"))
    declared = []
    for key, state in (config.get("tools") or {}).items():
        info = tools.tool_info(key)
        if info:
            declared.append({"key": key, "label": info[0], "category": info[1].key, "data": state.get("data", "none")})
    return {
        "sector_key": config.get("sector_key"),
        "sector_label": sectors.sector_label(config.get("sector_key")) or config.get("sector_custom"),
        "sector_custom": config.get("sector_custom"),
        "group": group.key,
        "group_label": group.label,
        "key_metrics": list(group.key_metrics),
        "typical_risks": list(group.typical_risks),
        "external_factors": list(group.external_factors),
        "vocabulary": dict(group.vocabulary),
        "next_questions": list(group.questions),
        "problems": config.get("problems"),
        "own_external_factors": config.get("external_factors"),
        "tools": declared,
        "custom_tools": config.get("custom_tools") or [],
    }


def integration_plan(config: dict) -> list[dict]:
    plan = []
    for key, state in (config.get("tools") or {}).items():
        info = tools.tool_info(key)
        if info is None:
            continue
        label, category = info
        plan.append({
            "key": key,
            "label": label,
            "category": category.key,
            "category_label": category.label,
            "data": list(category.data),
            "ai_use": category.ai_use,
            "export_help": tools.KNOWN_EXPORTS.get(key, category.export),
            "import_kinds": list(category.import_kinds),
            "direct_methods": list(category.direct),
            "status": "imported" if state.get("data") == "imported" else "to_connect",
            "last_import_at": state.get("last_import_at"),
        })
    return plan
