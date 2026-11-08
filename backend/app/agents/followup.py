"""What the AI started and did not finish, and the questions it asks to move on.

Two small mechanisms the agents share:

- an activity record: every flow started for the person (a browser task, an
  OAuth connection, a tool connection) is tracked as in progress / stopped /
  done. What stays unfinished comes back as a reminder in the decisions until
  it is finished or the person says they no longer want it;
- questions: when the Guide or the Analyste lack something (a document, a
  synchronisation never made, a web address before the browser acts), they ask,
  keep the answer in the company knowledge, and deduce the next tasks from it.
"""

import hashlib
import json
import re
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.agents import perplexity, veilleur_agent
from app.business_context.service import BusinessContextService
from app.configuration import service as config_service
from app.core.entities import AgentProposal, Company

MAX_ACTIVITY = 40
MAX_OPEN_QUESTIONS = 3
STALE_AFTER = timedelta(minutes=3)  # a flow in progress for this long without ending is unfinished
STATUSES = ("in_progress", "stopped", "done", "dismissed")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _agents_config(session: Session, company_id: uuid.UUID):
    context = BusinessContextService(session).get_or_create(company_id)
    config = dict(context.configuration or {})
    return context, config, dict(config.get("agents") or {})


# --- activity ----------------------------------------------------------------------

def track(session: Session, company_id: uuid.UUID, key: str, title: str, status: str, *, kind: str = "task", href: str | None = None, agent: str | None = None) -> None:
    """Create or update one tracked flow. A dismissed flow stays dismissed unless it starts again."""

    context, config, agents = _agents_config(session, company_id)
    items = [dict(i) for i in agents.get("activity") or []]
    current = next((i for i in items if i["key"] == key), None)
    if current is None:
        current = {"key": key, "kind": kind, "title": title[:200], "href": href, "agent": agent, "started_at": _now().isoformat()}
        items.append(current)
    elif current.get("status") == "dismissed" and status != "in_progress":
        return
    current.update(status=status, updated_at=_now().isoformat(), title=title[:200])
    if href:
        current["href"] = href
    agents["activity"] = items[-MAX_ACTIVITY:]
    config["agents"] = agents
    context.configuration = config
    session.add(context)
    session.commit()


def safe_track(company_id: uuid.UUID, key: str, title: str, status: str, **kwargs) -> None:
    """For callers without a session (browser threads): never raises."""

    from app.core.tenant_scope import scope_session
    from app.database import SessionLocal

    try:
        with SessionLocal() as db:
            scope_session(db, company_id)
            track(db, company_id, key, title, status, **kwargs)
    except Exception:
        pass


def activity(session: Session, company_id: uuid.UUID) -> dict:
    """Tracked flows, newest first, with the ones that were left unfinished."""

    from app.browser import manager

    _, _, agents = _agents_config(session, company_id)
    items = []
    for raw in agents.get("activity") or []:
        item = dict(raw)
        if item["key"].startswith("browser:") and item.get("status") == "in_progress":
            live = manager.TASKS.get(item["key"].split(":", 1)[1])
            if live is None:  # the server restarted: the task is gone
                item["status"] = "stopped"
        items.append(item)
    items.sort(key=lambda i: i.get("updated_at") or "", reverse=True)
    cutoff = _now() - STALE_AFTER
    unfinished = [
        i for i in items
        if i.get("status") == "stopped"
        or (i.get("status") == "in_progress" and not i["key"].startswith("browser:") and datetime.fromisoformat(i["updated_at"]) < cutoff)
    ]
    shown = [i for i in items if i.get("status") != "dismissed"]
    return {"items": shown, "unfinished": unfinished}


def dismiss(session: Session, company_id: uuid.UUID, key: str) -> None:
    context, config, agents = _agents_config(session, company_id)
    items = [dict(i) for i in agents.get("activity") or []]
    for item in items:
        if item["key"] == key:
            item["status"] = "dismissed"
            item["updated_at"] = _now().isoformat()
    agents["activity"] = items
    config["agents"] = agents
    context.configuration = config
    session.add(context)
    session.commit()


# --- questions ---------------------------------------------------------------------

def _open_questions(session: Session, company_id: uuid.UUID) -> int:
    return session.query(AgentProposal).filter_by(company_id=company_id, kind="missing_info", status="new").count()


def ask(session: Session, company: Company, agent: str, key: str, question: str, why: str) -> bool:
    """One question, once: it is not asked again after an answer or a dismissal."""

    dedupe = hashlib.sha1(f"q|{key}".encode()).hexdigest()
    if session.query(AgentProposal).filter_by(company_id=company.id, dedupe_key=dedupe).first():
        return False
    session.add(AgentProposal(
        company_id=company.id, agent=agent, kind="missing_info", category="question", title=question[:255], why=why[:1500],
        action_type="none", status="new", dedupe_key=dedupe,
    ))
    session.flush()
    return True


def gaps(session: Session, company: Company) -> list[tuple[str, str, str, str]]:
    """(agent, key, question, why) for what the AI cannot do without the person."""

    from app.configuration import tools as config_tools

    config = config_service.get_configuration(session, company.id)
    out: list[tuple[str, str, str, str]] = []
    known = " ".join(str(k.get("answer", "")) for k in config.get("agent_knowledge") or [])
    for key, state in (config.get("tools") or {}).items():
        info = config_tools.tool_info(key)
        if info is None:
            continue
        label, category = info
        if state.get("data") == "imported" or state.get("connection") == "connected":
            continue
        declared = state.get("connection_requested_at") or state.get("declared_at")
        if declared and datetime.fromisoformat(declared) < _now() - timedelta(days=2):
            out.append(("analyste", f"sync:{key}", f"Pourquoi la synchronisation de {label} n'est pas faite ?",
                        "Elle est demandée depuis plus de 2 jours sans résultat : bloqué par un accès, un manque de temps, ou autre chose ? Je propose une solution selon votre réponse."))
        elif category.import_kinds:
            if session.query(AgentProposal).filter_by(company_id=company.id, agent="guide", action_type="browser", status="new").filter(AgentProposal.action_payload["tool"].as_string() == label).first() and not known_url(session, company.id, label):
                out.append(("guide", f"url:{key}", f"Quelle est l'adresse web de connexion à {label} ?",
                            "Pour que le navigateur de l'IA aille directement au bon endroit (jamais de mot de passe : vous vous connectez vous-même)."))
            out.append(("guide", f"export:{key}", f"Savez-vous exporter vos données depuis {label}, ou qui peut le faire chez vous ?",
                        f"Si vous ne savez pas, je vous guide pas à pas, ou je laisse le navigateur de l'IA le faire pendant que vous suivez."))
    if not config.get("imports") and "document" not in known.lower():
        out.append(("analyste", "docs:none", "Quels documents avez-vous sous la main aujourd'hui (FEC, liste clients, fournisseurs, catalogue) ?",
                    "Sans aucun document, je ne peux analyser aucun chiffre : dites-moi ce qui existe et où, je m'occupe du reste."))
    return out


def ask_questions(session: Session, company: Company) -> int:
    created = 0
    for agent, key, question, why in gaps(session, company):
        if _open_questions(session, company.id) + created >= MAX_OPEN_QUESTIONS:
            break
        created += ask(session, company, agent, key, question, why)
    session.commit()
    return created


_DEDUCE_SYSTEM = (
    "Tu es un agent d'un logiciel de pilotage pour PME. Tu as posé une question à la personne, elle a répondu. "
    "Déduis-en : (1) au plus 2 tâches concrètes à lui proposer, (2) au plus UNE question de suivi si l'information reste insuffisante pour agir, (3) un fait court à retenir sur l'entreprise. "
    'Réponds UNIQUEMENT en JSON : {"tasks":[{"title":"","summary":"","action":"task|browser|none","text":""}],"follow_up":null,"learned":""}. '
    "Pas de tâche inventée : seulement ce qui découle de la réponse. Français, phrases courtes."
)


def deduce(session: Session, company: Company, proposal: AgentProposal, text: str) -> dict:
    """After an answer: learn, propose tasks, ask again if needed. Never fails the answer."""

    from app.agents import service

    result = {"tasks": 0, "follow_up": None, "learned": None}
    if not veilleur_agent.enabled():
        return result
    try:
        raw = perplexity.chat(_DEDUCE_SYSTEM, f"Question : {proposal.title}\nContexte : {proposal.why or ''}\nRéponse de la personne : {text}\nEntreprise : {company.name}")
        match = re.search(r"\{.*\}", raw, re.S)
        data = json.loads(match.group(0)) if match else {}
    except (perplexity.PerplexityError, ValueError):
        return result
    for t in (data.get("tasks") or [])[:2]:
        if not isinstance(t, dict) or not str(t.get("title") or "").strip():
            continue
        action = t.get("action") if t.get("action") in ("task", "browser") else "none"
        item = {"category": "suite", "title": t["title"], "summary": t.get("summary"), "why_it_matters": f"Déduit de votre réponse à : {proposal.title}",
                "suggested_action": {"type": action, "text": t.get("text") or t["title"]}}
        result["tasks"] += service._ingest(session, company, item, [], agent=proposal.agent)
    follow = str(data.get("follow_up") or "").strip()
    if follow and follow.lower() not in ("null", "none", "non") and _open_questions(session, company.id) < MAX_OPEN_QUESTIONS:
        if ask(session, company, proposal.agent, f"follow:{proposal.id}:{follow.lower()[:80]}", follow, f"Pour continuer après votre réponse à : {proposal.title}"):
            result["follow_up"] = follow
    learned = str(data.get("learned") or "").strip()
    if learned:
        context, config, _ = _agents_config(session, company.id)
        items = list(config.get("agent_knowledge") or [])
        items.append({"question": "Ce que l'IA a retenu de vos réponses", "answer": learned[:400], "at": _now().isoformat()})
        config["agent_knowledge"] = items[-60:]
        context.configuration = config
        session.add(context)
        result["learned"] = learned
    session.flush()
    return result


def known_url(session: Session, company_id: uuid.UUID, label: str) -> str | None:
    """A web address the person gave in an answer that mentions this tool."""

    for item in reversed(config_service.get_configuration(session, company_id).get("agent_knowledge") or []):
        if label.lower() in str(item.get("question", "")).lower():
            found = re.search(r"https?://\S+|\b[\w-]+(?:\.[\w-]+)+/?\S*", str(item.get("answer", "")))
            if found:
                return found.group(0).rstrip(".,;")
    return None
