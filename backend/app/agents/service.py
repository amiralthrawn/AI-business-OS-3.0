"""Agents: settings, runs, proposals, and the completion guide.

Autonomy is per kind of action and only covers what the product can really
do by itself today: put a date in the calendar, create a follow-up task.
Anything that leaves the company (an e-mail to clients or staff) is only
ever drafted: sending needs a connected mailbox, and until then the person
confirms the sending (see app.communications).
"""

import hashlib
import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.agents import perplexity, veilleur
from app.business_context.service import BusinessContextService
from app.configuration import service as config_service
from app.core.entities import (
    AgentProposal,
    AgentRun,
    CalendarEvent,
    Communication,
    Company,
    Customer,
    Product,
    Supplier,
    Task,
    Transaction,
    UserProfile,
)

ACTION_TYPES = ("calendar_event", "task")
DEFAULT_SETTINGS = {"enabled": True, "autonomy": {"calendar_event": "ask", "task": "ask"}}
PARIS = ZoneInfo("Europe/Paris")
MAX_TOPICS = 12


def now() -> datetime:
    return datetime.now(timezone.utc)


def aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


# --- settings ---------------------------------------------------------------

def get_settings(session: Session, company_id: uuid.UUID) -> dict:
    config = config_service.get_configuration(session, company_id)
    saved = config.get("agents") or {}
    autonomy = {**DEFAULT_SETTINGS["autonomy"], **{k: v for k, v in (saved.get("autonomy") or {}).items() if k in ACTION_TYPES and v in ("ask", "auto")}}
    return {"enabled": bool(saved.get("enabled", True)), "autonomy": autonomy, "watch_topics": watch_topics(saved)}


def watch_topics(saved: dict) -> list[str]:
    return [t for t in (saved.get("watch_topics") or []) if isinstance(t, str) and t.strip()][:MAX_TOPICS]


def set_watch_topics(session: Session, company_id: uuid.UUID, topics: list[str]) -> list[str]:
    """What the company asked the Veilleur to follow, in its own words."""

    cleaned: list[str] = []
    for topic in topics:
        text = " ".join(str(topic).split())[:300]
        if text and text.lower() not in (c.lower() for c in cleaned):
            cleaned.append(text)
    context = BusinessContextService(session).get_or_create(company_id)
    config = dict(context.configuration or {})
    agents = dict(config.get("agents") or {})
    agents["watch_topics"] = cleaned[:MAX_TOPICS]
    config["agents"] = agents
    context.configuration = config
    session.commit()
    return agents["watch_topics"]


def save_settings(session: Session, company_id: uuid.UUID, enabled: bool, autonomy: dict[str, str]) -> dict:
    context = BusinessContextService(session).get_or_create(company_id)
    config = dict(context.configuration or {})
    config["agents"] = {
        **(config.get("agents") or {}),
        "enabled": enabled,
        "autonomy": {k: ("auto" if autonomy.get(k) == "auto" else "ask") for k in ACTION_TYPES},
    }
    context.configuration = config
    session.commit()
    return get_settings(session, company_id)


def knowledge(session: Session, company_id: uuid.UUID) -> list[dict]:
    return list(config_service.get_configuration(session, company_id).get("agent_knowledge") or [])


# --- running agents -----------------------------------------------------------

def cadence_hours(at: datetime | None = None) -> int:
    """24h a day, not at the same pace: every 3 hours in the working day,
    every 8 hours at night (Paris time)."""

    hour = (at or now()).astimezone(PARIS).hour
    return 3 if 7 <= hour < 22 else 8


def last_run(session: Session, company_id: uuid.UUID, agent: str) -> AgentRun | None:
    return session.query(AgentRun).filter_by(company_id=company_id, agent=agent).order_by(AgentRun.created_at.desc()).first()


def is_due(session: Session, company_id: uuid.UUID, agent: str, hours: int) -> bool:
    run = last_run(session, company_id, agent)
    if run is None:
        return True
    return now() - aware(run.created_at) >= timedelta(hours=hours)


def run_veilleur(session: Session, company: Company) -> AgentRun:
    run = AgentRun(company_id=company.id, agent="veilleur", status="ok", found=0)
    session.add(run)
    if not perplexity.configured():
        run.status, run.message = "not_configured", "Aucune clé de recherche web n'est renseignée : le Veilleur ne cherche rien tant qu'elle manque."
        run.finished_at = now()
        session.commit()
        return run
    config = config_service.get_configuration(session, company.id)
    profile = veilleur.profile_text(company.name, company.website_url, config_service.ai_profile(config), knowledge(session, company.id))
    try:
        results = veilleur.scan(profile, company.name, date.today(), get_settings(session, company.id)["watch_topics"])
    except perplexity.PerplexityError as exc:
        run.status, run.message = "error", str(exc)[:300]
        run.finished_at = now()
        session.commit()
        return run
    created = 0
    for item, sources in results:
        created += 1 if _ingest(session, company, item, sources) else 0
    run.found = created
    run.message = f"{created} nouvelle(s) information(s)" if created else "Rien de nouveau"
    run.finished_at = now()
    session.commit()
    return run


def run_analyste(session: Session, company: Company) -> AgentRun:
    from app.event_bus import event_bus
    from app.core.events.tenant import TenantEventBus
    from app.intelligence.monitoring import run_monitoring_sweep

    run = AgentRun(company_id=company.id, agent="analyste", status="ok", found=0)
    session.add(run)
    result = run_monitoring_sweep(session, TenantEventBus(event_bus, company.id))
    run.found = result["risks_created"] + result["opportunities_created"]
    run.message = f"{result['risks_created']} risque(s), {result['opportunities_created']} opportunité(s)" if run.found else "Rien de nouveau dans vos chiffres"
    run.finished_at = now()
    session.commit()
    return run


def _ingest(session: Session, company: Company, item: dict, sources: list[str]) -> bool:
    title = str(item.get("title")).strip()[:255]
    when = veilleur.parse_date(item.get("date"))
    key = hashlib.sha1(f"{title.lower()}|{when.date() if when else ''}".encode()).hexdigest()
    if session.query(AgentProposal).filter_by(company_id=company.id, dedupe_key=key).first():
        return False
    suggestion = item.get("suggested_action") if isinstance(item.get("suggested_action"), dict) else {}
    action = suggestion.get("type") if suggestion.get("type") in ACTION_TYPES else "none"
    if action == "calendar_event" and when is None:
        action = "task"
    category = str(item.get("category") or "autre")[:40]
    proposal = AgentProposal(
        company_id=company.id, agent="veilleur", kind="finding", category=category, title=title,
        summary=str(item.get("summary") or "")[:1500] or None, why=str(item.get("why_it_matters") or "")[:1500] or None,
        sources=sources[:6], event_date=when, action_type=action,
        action_payload={"text": str(suggestion.get("text") or title)[:255]} if action != "none" else None,
        status="new", dedupe_key=key,
    )
    session.add(proposal)
    session.flush()
    needs = str(item.get("needs_info") or "").strip()
    if needs and needs.lower() not in ("null", "none", "non"):
        session.add(AgentProposal(
            company_id=company.id, agent="veilleur", kind="missing_info", category="information", title=needs[:255],
            why=f"Nécessaire pour traiter : {title}", action_type="none", status="new",
            dedupe_key=hashlib.sha1(f"need|{needs.lower()}".encode()).hexdigest(),
        ))
    if action != "none" and get_settings(session, company.id)["autonomy"].get(action) == "auto":
        execute(session, proposal, automatic=True)
    session.flush()
    return True


# --- acting on proposals --------------------------------------------------------

def execute(session: Session, proposal: AgentProposal, *, automatic: bool) -> None:
    ref: dict = {}
    payload = proposal.action_payload or {}
    if proposal.action_type == "calendar_event" and proposal.event_date:
        event = CalendarEvent(
            company_id=proposal.company_id, title=proposal.title[:200], kind="other", starts_at=proposal.event_date, all_day=True,
            notes=(proposal.summary or "")[:2000] or None, source="veilleur",
        )
        session.add(event)
        session.flush()
        ref["calendar_event"] = str(event.id)
    elif proposal.action_type == "task":
        from app.actions.service import ActionsService
        from app.event_bus import event_bus
        from app.core.events.tenant import TenantEventBus

        task = ActionsService(session, TenantEventBus(event_bus, proposal.company_id)).create_manual_task(
            company_id=proposal.company_id, title=str(payload.get("text") or proposal.title)[:255],
            description=f"Proposé par le Veilleur : {proposal.title}. {proposal.summary or ''}".strip(),
        )
        ref["task"] = str(task.id)
    proposal.result_ref = ref or None
    proposal.status = "auto_done" if automatic else "accepted"
    proposal.decided_at = now()


def undo(session: Session, proposal: AgentProposal) -> None:
    ref = proposal.result_ref or {}
    if ref.get("calendar_event"):
        event = session.get(CalendarEvent, uuid.UUID(ref["calendar_event"]))
        if event is not None:
            session.delete(event)
    if ref.get("task"):
        task = session.get(Task, uuid.UUID(ref["task"]))
        if task is not None:
            from app.core.entities.task import TaskStatus
            task.status = TaskStatus.CANCELLED
    proposal.status = "undone"
    proposal.decided_at = now()


def answer(session: Session, proposal: AgentProposal, text: str) -> None:
    context = BusinessContextService(session).get_or_create(proposal.company_id)
    config = dict(context.configuration or {})
    items = list(config.get("agent_knowledge") or [])
    items.append({"question": proposal.title, "answer": text.strip()[:1000], "at": now().isoformat()})
    config["agent_knowledge"] = items[-60:]
    context.configuration = config
    proposal.answer = text.strip()[:1000]
    proposal.status = "answered"
    proposal.decided_at = now()


# --- completion guide -----------------------------------------------------------

def guide(session: Session, company: Company) -> dict:
    config = config_service.get_configuration(session, company.id)
    tools = config.get("tools") or {}
    answers = config.get("answers") or {}
    def _category(key: str) -> str | None:
        info = config_service.tools.tool_info(key)
        return info[1].key if info else None

    messaging = any(state.get("data", "none") != "none" for key, state in tools.items() if _category(key) == "messaging")
    count = lambda model: session.query(model).count()
    imports = {e.get("kind") for e in (config.get("imports") or [])}
    checks = [
        (10, bool(company.industry), "Dire quel est votre métier", "Pour que l'IA parle votre langage et surveille les bons sujets.", "/settings"),
        (10, any(answers.get(k) for k in ("goals", "problems", "externals")), "Répondre aux questions sur vos objectifs et vos difficultés", "Pour que chaque recommandation serve vos vrais objectifs.", "/settings"),
        (10, bool(tools), "Indiquer les outils que vous utilisez", "Pour que l'IA sache d'où viennent vos chiffres et comment les récupérer.", "/settings"),
        (10, count(Customer) > 0, "Déposer votre liste de clients", "Sans clients, pas de suivi des baisses d'activité ni d'opportunités.", "/settings"),
        (10, count(Supplier) > 0, "Déposer votre liste de fournisseurs", "Pour suivre les retards de livraison et comparer les prix.", "/settings"),
        (10, count(Product) > 0, "Déposer votre catalogue de produits", "Pour calculer vos marges produit par produit.", "/settings"),
        (15, count(Transaction) > 0, "Déposer vos ventes et vos achats (ou votre FEC)", "C'est ce qui permet à l'IA de détecter risques et opportunités avec vos vrais chiffres.", "/settings"),
        (5, "fec" in imports, "Déposer votre comptabilité (FEC)", "Donne une vue exacte de votre chiffre d'affaires et de vos charges.", "/settings"),
        (10, session.query(UserProfile).count() > 1, "Inviter votre équipe", "Chacun voit ce qui le concerne et peut valider ses décisions.", "/people"),
        (5, messaging or count(Communication) > 0, "Relier vos e-mails et votre messagerie", "L'IA pourra analyser et prioriser vos échanges.", "/settings"),
        (5, bool(company.website_url), "Renseigner votre site web", "Le Veilleur contrôlera votre visibilité en ligne.", "/settings"),
        (10, perplexity.configured(), "Activer le Veilleur (clé de recherche web)", "Sans elle, aucune recherche externe : salons, prix, concurrents, avis Google.", "/settings#agents"),
    ]
    total = sum(w for w, *_ in checks)
    done = sum(w for w, ok, *_ in checks if ok)
    steps = [{"title": t, "why": why, "href": href, "weight": w} for w, ok, t, why, href in checks if not ok]
    return {"percent": round(100 * done / total), "steps": steps}
