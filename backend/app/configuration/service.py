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
    answers: dict[str, list[str]] | None = None,
    answer_notes: dict[str, str] | None = None,
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
    first_time = "completed_at" not in config
    config.setdefault("completed_at", datetime.now(timezone.utc).isoformat())

    # Multiple-choice answers (sectors.QCM): kept as ticked, with an optional
    # free precision per question. They also feed the plain-text fields the
    # rest of the product already reads.
    if answers is not None:
        config["answers"] = {
            key: [str(a).strip()[:200] for a in values if str(a).strip()][:12]
            for key, values in answers.items()
            if key in sectors.QCM_TITLES and isinstance(values, list)
        }
    if answer_notes is not None:
        config["answer_notes"] = {key: str(note).strip()[:2000] for key, note in answer_notes.items() if key in sectors.QCM_TITLES and str(note).strip()}
    if answers is not None or answer_notes is not None:
        picked, notes = config.get("answers", {}), config.get("answer_notes", {})

        def _compose(key: str) -> str:
            text = "; ".join(picked.get(key, []))
            return f"{text}. {notes[key]}" if text and key in notes else text or notes.get(key, "")

        if _compose("goals"):
            objectives = _compose("goals")
        if _compose("problems") and problems is None:
            config["problems"] = _compose("problems")
        if _compose("externals") and external_factors is None:
            config["external_factors"] = _compose("externals")

    # The sector shown everywhere in the product is the company's own words
    # when it chose "Autre", else the catalogue label.
    label = sectors.sector_label(config.get("sector_key"))
    if config.get("sector_key") == "autre" and config.get("sector_custom"):
        label = config["sector_custom"]
    if label:
        company.industry = label[:255]
        session.add(company)

    if functions is None and first_time:
        # The AI watches everything: that is the product. Nothing to choose.
        functions = list(FUNCTION_KEYS)
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
        "answers": config.get("answers") or {},
        "answer_notes": config.get("answer_notes") or {},
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
            "connection": state.get("connection"),
        })
    return plan


def request_connection(session: Session, company_id: uuid.UUID, tool_key: str) -> dict:
    """The company asks to be helped to connect a tool directly (secure,
    read-only authorisation). Recorded on the tool; nothing is connected."""

    context = BusinessContextService(session).get_or_create(company_id)
    config = dict(context.configuration or {})
    configured = dict(config.get("tools") or {})
    if tool_key not in configured:
        raise KeyError(tool_key)
    state = dict(configured[tool_key])
    state["connection"] = "requested"
    state["connection_requested_at"] = datetime.now(timezone.utc).isoformat()
    configured[tool_key] = state
    config["tools"] = configured
    context.configuration = config
    session.add(context)
    session.commit()
    return state
