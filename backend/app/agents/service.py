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

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agents import perplexity, veilleur, veilleur_agent
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
    config = config_service.get_configuration(session, company_id)
    items = list(config.get("agent_knowledge") or [])
    site = (config.get("website") or {}).get("analysis")
    if site:
        offer = ", ".join(site.get("offer") or [])[:500]
        items.append({"question": "Que montre le site web de l'entreprise (analysé par l'Analyste) ?", "answer": f"{site.get('summary', '')} Offre : {offer}. Public : {site.get('audience', '')}"[:1400]})
    return items


# --- which model does each agent use, and requests to change it ---------------

AGENT_LABELS = {
    "veilleur": "Veilleur",
    "analyste": "Analyste",
    "guide": "Guide de connexion",
}


def routes(agent: str) -> list[dict]:
    """Which model handles which kind of request. Each step of an agent is sent
    to the model that fits it (reasoning, web search, plain calculation)."""

    from app.config import get_settings as app_settings

    settings = app_settings()
    if not (settings.openrouter_api_key or "").strip():
        return []
    if agent == "veilleur":
        return [
            {"task": "Comprendre votre demande, raisonner, rédiger la réponse, choisir les outils", "model": settings.openrouter_agent_model},
            {"task": "Chercher sur le web avec sources (prix, salons, concurrents, actualités)", "model": settings.openrouter_model},
            {"task": "Lire une page web que vous indiquez (OEMsTrade, Accuris…)", "model": None},
            {"task": "Comparer avec vos produits, stocks, fournisseurs, clients (Analyste)", "model": None},
        ]
    if agent == "guide":
        return [
            {"task": "Rechercher la procédure d'export d'un logiciel, avec sources", "model": settings.openrouter_model},
            {"task": "Répondre à une question sur un logiciel, avec sources", "model": settings.openrouter_model},
            {"task": "Suggérer l'étape suivante après un import", "model": None},
        ]
    return [
        {"task": "Détecter les risques et opportunités dans vos chiffres", "model": None},
        {"task": "Lire et comprendre votre site web en profondeur, proposer des améliorations", "model": settings.openrouter_agent_model},
    ]


def model_in_use(agent: str) -> dict:
    """What really powers an agent today. The two web agents (Veilleur, Guide)
    share the search provider; the Analyste is plain calculation on the
    company's figures and uses no language model."""

    from app.config import get_settings as app_settings

    settings = app_settings()
    out = _model_in_use(agent, settings)
    return {**out, "routes": routes(agent)}


def _model_in_use(agent: str, settings) -> dict:
    if agent == "analyste":
        if (settings.openrouter_api_key or "").strip():
            return {"provider": "Calculs internes + OpenRouter", "model": settings.openrouter_agent_model, "kind": "rules", "note": "Règles et statistiques sur vos chiffres (sans IA) ; un modèle de langage lit votre site web."}
        return {"provider": "Calculs internes", "model": None, "kind": "rules", "note": "Aucun modèle de langage : règles et statistiques sur vos chiffres."}
    if (settings.openrouter_api_key or "").strip():
        if agent == "veilleur":
            return {"provider": "OpenRouter", "model": settings.openrouter_agent_model, "kind": "agent", "note": f"IA générative avec outils : lit les sites, cherche sur le web ({settings.openrouter_model}), interroge l'Analyste et enregistre ses trouvailles."}
        return {"provider": "OpenRouter", "model": settings.openrouter_model, "kind": "web_search", "note": "Recherche web avec sources."}
    if (settings.gemini_api_key or "").strip():
        return {"provider": "Google Gemini", "model": settings.gemini_model, "kind": "web_search", "note": "Recherche web avec sources (Google Search)."}
    if (settings.perplexity_api_key or "").strip():
        return {"provider": "Perplexity", "model": settings.perplexity_model if "/" in (settings.perplexity_model or "") else "Agent API (fast)", "kind": "web_search", "note": "Recherche web avec sources."}
    return {"provider": None, "model": None, "kind": "web_search", "note": "Aucune clé de recherche renseignée : cet agent ne peut pas chercher."}


# --- memory: what each agent keeps of its previous exchanges ----------------------

MEMORY_KEEP = 30


def remember(session: Session, company_id: uuid.UUID, agent: str, request: str, answer: str, saved: list[str] | None = None) -> None:
    context = BusinessContextService(session).get_or_create(company_id)
    config = dict(context.configuration or {})
    agents = dict(config.get("agents") or {})
    memory = dict(agents.get("memory") or {})
    entry = {"at": now().isoformat(), "request": " ".join(request.split())[:300], "answer": " ".join(answer.split())[:700], "saved": [t[:120] for t in (saved or [])[:6]]}
    memory[agent] = [*(memory.get(agent) or []), entry][-MEMORY_KEEP:]
    agents["memory"] = memory
    config["agents"] = agents
    context.configuration = config
    session.commit()


def memory_items(session: Session, company_id: uuid.UUID, agent: str) -> list[dict]:
    return list(((config_service.get_configuration(session, company_id).get("agents") or {}).get("memory") or {}).get(agent) or [])


def recall(session: Session, company_id: uuid.UUID, agent: str, n: int = 6, only: str | None = None) -> str:
    """The latest exchanges, as text an agent can read before it answers."""

    items = [i for i in memory_items(session, company_id, agent) if not only or only.lower() in i["request"].lower()][-n:]
    if not items:
        return ""
    return "\n".join(
        f"- {datetime.fromisoformat(i['at']).astimezone(PARIS).strftime('%d/%m')} : demande « {i['request']} » -> {i['answer']}" + (f" (enregistré : {'; '.join(i['saved'])})" if i.get("saved") else "")
        for i in items
    )


def forget(session: Session, company_id: uuid.UUID, agent: str) -> None:
    context = BusinessContextService(session).get_or_create(company_id)
    config = dict(context.configuration or {})
    agents = dict(config.get("agents") or {})
    memory = dict(agents.get("memory") or {})
    memory.pop(agent, None)
    agents["memory"] = memory
    config["agents"] = agents
    context.configuration = config
    session.commit()


def model_requests(session: Session, company_id: uuid.UUID) -> list[dict]:
    saved = config_service.get_configuration(session, company_id).get("agents") or {}
    return list(saved.get("model_requests") or [])[-20:]


def request_model_change(session: Session, company_id: uuid.UUID, agent: str, wanted: str, reason: str | None) -> dict:
    """Recorded, never applied by itself: a model change is a decision on our
    side (cost, contract, quality). The request is shown with its status."""

    if agent not in AGENT_LABELS:
        raise KeyError(agent)
    entry = {
        "id": uuid.uuid4().hex[:12], "agent": agent, "current": model_in_use(agent),
        "wanted": " ".join(wanted.split())[:200], "reason": " ".join((reason or "").split())[:500] or None,
        "status": "requested", "at": now().isoformat(),
    }
    context = BusinessContextService(session).get_or_create(company_id)
    config = dict(context.configuration or {})
    agents = dict(config.get("agents") or {})
    agents["model_requests"] = [*(agents.get("model_requests") or []), entry][-20:]
    config["agents"] = agents
    context.configuration = config
    session.commit()
    return entry


def recent_runs(session: Session, company_id: uuid.UUID, agent: str, limit: int = 5) -> list[dict]:
    rows = session.query(AgentRun).filter_by(company_id=company_id, agent=agent).order_by(AgentRun.created_at.desc()).limit(limit).all()
    return [{"status": r.status, "found": r.found, "message": r.message, "at": r.created_at.isoformat()} for r in rows]


def log_run(session: Session, company_id: uuid.UUID, agent: str, status: str, message: str, found: int = 0) -> None:
    session.add(AgentRun(company_id=company_id, agent=agent, status=status, found=found, message=message[:400], finished_at=now()))
    session.commit()
    _book_usage(session, company_id, agent, perplexity.drain_usage())


# --- consumption: tokens and cost per agent --------------------------------------

# Indicative public prices, USD per million tokens (input, output) and per
# request for models that bill searches. The provider's own invoiced cost is
# used whenever the answer carries it.
PRICES = {
    "perplexity/sonar": {"in": 1.0, "out": 1.0, "request": 0.005},
    "perplexity/sonar-pro": {"in": 3.0, "out": 15.0, "request": 0.006},
    "gemini-3.5-flash-lite": {"in": 0.10, "out": 0.40, "request": 0.0},
    "google/gemini-2.5-flash": {"in": 0.30, "out": 2.50, "request": 0.0},
}


def model_catalog() -> list[dict]:
    """Models a company can ask for, with indicative prices (cheapest first)."""

    labels = {"perplexity/sonar": "Perplexity Sonar (économique)", "perplexity/sonar-pro": "Perplexity Sonar Pro (plus précis)", "gemini-3.5-flash-lite": "Google Gemini Flash-Lite (le moins cher)", "google/gemini-2.5-flash": "Google Gemini 2.5 Flash (agent génératif)"}
    rows = [{"model": m, "label": labels.get(m, m), "usd_per_m_in": p["in"], "usd_per_m_out": p["out"], "usd_per_request": p["request"]} for m, p in PRICES.items()]
    return sorted(rows, key=lambda r: r["usd_per_m_in"] + r["usd_per_m_out"] + r["usd_per_request"] * 200)


def _cost(entry: dict) -> float:
    if entry.get("cost") is not None:
        return float(entry["cost"])
    price = PRICES.get(entry.get("model") or "")
    if not price:
        return 0.0
    return (entry["tin"] * price["in"] + entry["tout"] * price["out"]) / 1_000_000 + price["request"]


def used_summary(entries: list[dict]) -> list[dict]:
    """Which models answered one request, with tokens and cost."""

    by: dict[str, dict] = {}
    for e in entries:
        row = by.setdefault(e["model"], {"model": e["model"], "calls": 0, "tokens": 0, "usd": 0.0})
        row["calls"] += 1
        row["tokens"] += e["tin"] + e["tout"]
        row["usd"] = round(row["usd"] + _cost(e), 6)
    return list(by.values())


def _book_usage(session: Session, company_id: uuid.UUID, agent: str, entries: list[dict]) -> None:
    if not entries:
        return
    context = BusinessContextService(session).get_or_create(company_id)
    config = dict(context.configuration or {})
    agents = dict(config.get("agents") or {})
    usage = dict(agents.get("usage") or {})
    mine = dict(usage.get(agent) or {})
    by_model = dict(mine.get("by_model") or {})
    for e in entries:
        row = dict(by_model.get(e["model"]) or {"calls": 0, "tin": 0, "tout": 0, "usd": 0.0})
        row["calls"] += 1
        row["tin"] += e["tin"]
        row["tout"] += e["tout"]
        row["usd"] = round(row["usd"] + _cost(e), 6)
        by_model[e["model"]] = row
    mine["by_model"] = by_model
    usage[agent] = mine
    agents["usage"] = usage
    config["agents"] = agents
    context.configuration = config
    session.commit()


def usage_summary(session: Session, company_id: uuid.UUID) -> dict:
    saved = (config_service.get_configuration(session, company_id).get("agents") or {}).get("usage") or {}
    agents: dict[str, dict] = {}
    for key in AGENT_LABELS:
        models = [{"model": m, **row} for m, row in ((saved.get(key) or {}).get("by_model") or {}).items()]
        agents[key] = {
            "calls": sum(r["calls"] for r in models), "tokens_in": sum(r["tin"] for r in models), "tokens_out": sum(r["tout"] for r in models),
            "usd": round(sum(r["usd"] for r in models), 4), "models": models,
        }
    return {
        "agents": agents,
        "total": {"calls": sum(a["calls"] for a in agents.values()), "tokens": sum(a["tokens_in"] + a["tokens_out"] for a in agents.values()), "usd": round(sum(a["usd"] for a in agents.values()), 4)},
        "catalog": model_catalog(),
    }


def ask_veilleur(session: Session, company: Company, request: str, follow: bool, context: str | None = None, with_analysis: bool = False) -> dict:
    """A direct request to the Veilleur: search this subject now, return what
    was found, and (optionally) keep following it."""

    if veilleur_agent.enabled():
        shared = 0
        if with_analysis:
            from app.agents import dossier

            last = last_analysis(session, company.id)
            context = (f"Résumé de la dernière analyse : {last['summary']}\n\n" if last else "") + dossier.build(session, company.id, request)
            shared = len(context)
        out = _ask_veilleur_agent(session, company, request, follow, context)
        out["shared_chars"] = shared
        return out
    if not perplexity.configured():
        log_run(session, company.id, "veilleur", "not_configured", f"Demande : {request[:120]} : aucune clé de recherche.")
        return {"status": "not_configured", "found": [], "message": "Aucune clé de recherche web n'est renseignée : le Veilleur ne peut pas chercher."}
    if follow:
        set_watch_topics(session, company.id, [*get_settings(session, company.id)["watch_topics"], request])
    config = config_service.get_configuration(session, company.id)
    profile = veilleur.profile_text(company.name, company.website_url, config_service.ai_profile(config), knowledge(session, company.id))
    try:
        results = veilleur.scan_topics(profile, [request], date.today())
    except perplexity.PerplexityError as exc:
        log_run(session, company.id, "veilleur", "error", f"Demande : {request[:120]} : {str(exc)[:200]}")
        return {"status": "error", "found": [], "message": str(exc)[:300]}
    shown = []
    for item, sources in results:
        _ingest(session, company, item, sources)
        shown.append({"title": str(item.get("title"))[:255], "summary": str(item.get("summary") or "")[:600], "why": str(item.get("why_it_matters") or "")[:400], "sources": sources[:5]})
    message = f"{len(shown)} résultat(s) pour : {request[:120]}" if shown else f"Rien de fiable trouvé pour : {request[:120]}"
    session.commit()
    log_run(session, company.id, "veilleur", "ok", message, len(shown))
    return {"status": "ok", "found": shown, "message": message}


def _ask_veilleur_agent(session: Session, company: Company, request: str, follow: bool, context: str | None = None) -> dict:
    if follow:
        set_watch_topics(session, company.id, [*get_settings(session, company.id)["watch_topics"], request])
    config = config_service.get_configuration(session, company.id)
    profile = veilleur.profile_text(company.name, company.website_url, config_service.ai_profile(config), knowledge(session, company.id))
    past = recall(session, company.id, "veilleur")
    if past:
        profile += f"\n\nMémoire de tes échanges précédents avec ce client (appuie-toi dessus, ne refais pas ce qui est déjà fait, signale ce qui a changé) :\n{past}"
    analyse = last_analysis(session, company.id)
    if analyse and not context:
        profile += f"\n\nDernière analyse de l'Analyste : {analyse['summary']}"
    perplexity.drain_usage()
    try:
        out = veilleur_agent.run(session, company, profile, (f"Analyse transmise par l'Analyste (à utiliser pour orienter ta recherche) :\n{context.strip()[:4000]}\n\nDemande : {request}" if context and context.strip() else request), lambda item, sources: _ingest(session, company, item, sources))
    except perplexity.PerplexityError as exc:
        session.rollback()
        log_run(session, company.id, "veilleur", "error", f"Demande : {request[:120]} : {str(exc)[:200]}")
        return {"status": "error", "found": [], "message": str(exc)[:300]}
    session.commit()
    used = used_summary(perplexity.peek_usage())
    remember(session, company.id, "veilleur", request, out["answer"], [f["title"] for f in out["found"]])
    log_run(session, company.id, "veilleur", "ok", f"Demande : {request[:140]} ({len(out['found'])} information(s) enregistrée(s))", len(out["found"]))
    return {"status": "ok", "found": out["found"], "message": out["answer"] or "Recherche terminée.", "used": used}


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


def _situation(session: Session, company_id: uuid.UUID) -> dict:
    from app.core.entities import Opportunity, Risk

    risks = session.query(Risk.id, Risk.title).filter(Risk.company_id == company_id).all()
    opps = session.query(Opportunity.id, Opportunity.title).filter(Opportunity.company_id == company_id).all()
    return {
        "risks": {str(i): t for i, t in risks[-500:]}, "opportunities": {str(i): t for i, t in opps[-500:]},
        "transactions": session.query(func.count(Transaction.id)).filter_by(company_id=company_id).scalar() or 0,
        "products": session.query(func.count(Product.id)).filter_by(company_id=company_id).scalar() or 0,
        "customers": session.query(func.count(Customer.id)).filter_by(company_id=company_id).scalar() or 0,
    }


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def analyste_summary(before: dict | None, after: dict, at: str | None) -> tuple[bool, str]:
    """(changed, 2-3 sentences). Deterministic: every claim is a difference
    between the two recorded situations."""

    when = datetime.fromisoformat(at).astimezone(PARIS).strftime("%d/%m à %H:%M") if at else None
    if before is None:
        return True, (f"Première analyse : {_plural(len(after['risks']), 'risque', 'risques')} et {_plural(len(after['opportunities']), 'opportunité', 'opportunités')} repéré(e)s "
                      f"sur {_plural(after['transactions'], 'transaction', 'transactions')}, {_plural(after['products'], 'produit', 'produits')} et {_plural(after['customers'], 'client', 'clients')}.")
    new_risks = [t for i, t in after["risks"].items() if i not in before.get("risks", {})]
    new_opps = [t for i, t in after["opportunities"].items() if i not in before.get("opportunities", {})]
    grown = {k: after[k] - before.get(k, 0) for k in ("transactions", "products", "customers")}
    if not new_risks and not new_opps and not any(grown.values()):
        return False, f"Rien n'a changé depuis la dernière analyse ({when}) : aucun nouveau risque ni opportunité, et vos données sont les mêmes."
    parts = []
    if new_risks:
        parts.append(f"{_plural(len(new_risks), 'nouveau risque', 'nouveaux risques')} : {'; '.join(new_risks[:3])}.")
    if new_opps:
        parts.append(f"{_plural(len(new_opps), 'nouvelle opportunité', 'nouvelles opportunités')} : {'; '.join(new_opps[:3])}.")
    data = [f"{'+' if v > 0 else ''}{v} {label}" for v, label in ((grown["transactions"], "transaction(s)"), (grown["products"], "produit(s)"), (grown["customers"], "client(s)")) if v]
    if data:
        parts.append(f"Vos données ont évolué depuis le {when} : {', '.join(data)}.")
    if not new_risks and not new_opps:
        parts.append("Aucun nouveau risque ni opportunité n'en découle pour l'instant.")
    else:
        parts.append(f"Au total : {_plural(len(after['risks']), 'risque', 'risques')} et {_plural(len(after['opportunities']), 'opportunité', 'opportunités')} suivi(e)s.")
    return True, " ".join(parts)


def last_analysis(session: Session, company_id: uuid.UUID) -> dict | None:
    return (config_service.get_configuration(session, company_id).get("agents") or {}).get("analyste_last")


def run_analyste(session: Session, company: Company) -> AgentRun:
    from app.event_bus import event_bus
    from app.core.events.tenant import TenantEventBus
    from app.intelligence.monitoring import run_monitoring_sweep

    previous = last_analysis(session, company.id)
    run = AgentRun(company_id=company.id, agent="analyste", status="ok", found=0)
    session.add(run)
    result = run_monitoring_sweep(session, TenantEventBus(event_bus, company.id))
    run.found = result["risks_created"] + result["opportunities_created"]
    after = _situation(session, company.id)
    changed, summary = analyste_summary(previous["situation"] if previous else None, after, previous["at"] if previous else None)
    run.message = summary[:400]
    run.finished_at = now()
    context = BusinessContextService(session).get_or_create(company.id)
    config = dict(context.configuration or {})
    agents = dict(config.get("agents") or {})
    agents["analyste_last"] = {"at": now().isoformat(), "summary": summary, "changed": changed, "situation": after}
    config["agents"] = agents
    context.configuration = config
    session.commit()
    remember(session, company.id, "analyste", "Analyse de vos données", summary)
    _refresh_site(session, company)
    return run


def _refresh_site(session: Session, company: Company) -> None:
    """A standing task: the site is re-read every week, so the proposals follow it."""

    from app.website import intelligence

    if not company.website_url:
        return
    saved = (config_service.get_configuration(session, company.id).get("website") or {})
    at = saved.get("analysed_at")
    if at and now() - datetime.fromisoformat(at) < timedelta(days=7):
        return
    try:
        intelligence.integrate(session, company)
    except (intelligence.SiteError, perplexity.PerplexityError):
        session.rollback()


def _ingest(session: Session, company: Company, item: dict, sources: list[str], agent: str = "veilleur") -> bool:
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
        company_id=company.id, agent=agent, kind="finding", category=category, title=title,
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
    site = config.get("website") or {}
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
        (10, bool(company.website_url) or bool(site.get("request")), "Ajouter le site web de l'entreprise (ou nous demander d'en créer un)", "L'Analyste lit votre site en profondeur pour comprendre votre métier et partage ce qu'il comprend avec les autres agents.", "/communications?tab=website"),
        (5, bool(site.get("analysis")) or not company.website_url, "Faire analyser votre site web", "Sans analyse, aucune amélioration ni synchronisation ne peut vous être proposée.", "/communications?tab=website"),
        (10, perplexity.configured(), "Activer le Veilleur (clé de recherche web)", "Sans elle, aucune recherche externe : salons, prix, concurrents, avis Google.", "/settings#agents"),
    ]
    total = sum(w for w, *_ in checks)
    done = sum(w for w, ok, *_ in checks if ok)
    steps = [{"title": t, "why": why, "href": href, "weight": w} for w, ok, t, why, href in checks if not ok]
    return {"percent": round(100 * done / total), "steps": steps}
