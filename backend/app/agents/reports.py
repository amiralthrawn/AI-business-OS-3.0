"""Reports: what an agent did, in words, when it finishes.

Every long piece of work ends with a report the person can open, with the
next steps it suggests. Unread reports are what the notification pills show.
"""

import uuid

from sqlalchemy.orm import Session

from app.business_context.service import BusinessContextService
from app.configuration import service as config_service

KEEP = 30


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def add(session: Session, company_id: uuid.UUID, agent: str, title: str, text: str, next_steps: list[dict] | None = None) -> str:
    """next_steps: {"label", "href"} (a page) or {"label", "relay": "request"} (hand the analysis to the Veilleur)."""

    context = BusinessContextService(session).get_or_create(company_id)
    config = dict(context.configuration or {})
    agents = dict(config.get("agents") or {})
    report_id = uuid.uuid4().hex[:12]
    agents["reports"] = [*(agents.get("reports") or []), {"id": report_id, "agent": agent, "title": title[:200], "text": text[:6000], "at": _now(), "read": False, "next": (next_steps or [])[:4]}][-KEEP:]
    config["agents"] = agents
    context.configuration = config
    session.add(context)
    session.commit()
    return report_id


def listing(session: Session, company_id: uuid.UUID) -> list[dict]:
    items = list(((config_service.get_configuration(session, company_id).get("agents") or {}).get("reports")) or [])
    return list(reversed(items))


def mark_read(session: Session, company_id: uuid.UUID, report_id: str | None = None) -> None:
    """One report, or all of them when no id is given."""

    context = BusinessContextService(session).get_or_create(company_id)
    config = dict(context.configuration or {})
    agents = dict(config.get("agents") or {})
    items = [dict(r) for r in agents.get("reports") or []]
    for r in items:
        if report_id is None or r["id"] == report_id:
            r["read"] = True
    agents["reports"] = items
    config["agents"] = agents
    context.configuration = config
    session.add(context)
    session.commit()
