"""The Directeur: the one who keeps the company's AI team busy.

It sees every agent, the open questions, the unfinished tasks and the state of
the data. At each round it decides what is worth doing next: ask the person a
question, propose an initiative, start an agent that has been idle, and it
keeps a journal of what it decided so the person can follow its reasoning.
Without a language model it still works from rules; with one it also proposes
initiatives of its own. It never sends anything outside the company.
"""

import json
import re
import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from app.agents import followup, perplexity, progress, service, veilleur_agent
from app.business_context.service import BusinessContextService
from app.configuration import service as config_service
from app.core.entities import AgentProposal, Company, Customer, Product, Supplier, Transaction

JOURNAL_KEEP = 20
MAX_INITIATIVES = 2

_SYSTEM = (
    "Tu es le Directeur de l'équipe d'IA d'une PME : tu vois toute l'activité du logiciel et de tes agents (Veilleur, Analyste, Guide, Exécutant, Navigateur) et tu fais vivre l'entreprise. "
    "À partir de l'état fourni, décide de ce qui mérite d'être fait maintenant. Réponds UNIQUEMENT en JSON : "
    '{"message":"2 phrases : où en est l\'entreprise et ce que tu fais maintenant","initiatives":[{"title":"","summary":"","why":"","action":"task|browser|none","text":""}],"question":null}. '
    "Au plus 2 initiatives concrètes, jamais inventées : elles découlent des données ou des réponses connues. Une seule question si une information clé manque. Français, direct, sans jargon."
)


def _state(session: Session, company: Company) -> dict:
    config = config_service.get_configuration(session, company.id)
    agents_cfg = config.get("agents") or {}
    runs = {}
    for key in service.AGENT_LABELS:
        run = service.last_run(session, company.id, key)
        if run:
            runs[key] = {"status": run.status, "message": (run.message or "")[:120], "hours_ago": round((service.now() - service.aware(run.created_at)).total_seconds() / 3600, 1)}
    guide = service.guide(session, company)
    return {
        "company": company.name,
        "sector": company.industry,
        "counts": {"transactions": session.query(Transaction).count(), "customers": session.query(Customer).count(), "suppliers": session.query(Supplier).count(), "products": session.query(Product).count()},
        "configured_percent": guide["percent"],
        "missing": [s["title"] for s in guide["steps"][:5]],
        "agents": runs,
        "open_proposals": session.query(AgentProposal).filter_by(company_id=company.id, status="new", kind="finding").count(),
        "open_questions": session.query(AgentProposal).filter_by(company_id=company.id, status="new", kind="missing_info").count(),
        "unfinished": [i["title"] for i in followup.activity(session, company.id)["unfinished"]][:5],
        "known": [f"{k.get('question', '')[:80]} -> {k.get('answer', '')[:120]}" for k in (config.get("agent_knowledge") or [])[-8:]],
        "journal": [e["text"][:160] for e in (agents_cfg.get("directeur_log") or [])[-3:]],
    }


def journal(session: Session, company_id: uuid.UUID) -> list[dict]:
    return list(((config_service.get_configuration(session, company_id).get("agents") or {}).get("directeur_log")) or [])


def _write(session: Session, company_id: uuid.UUID, text: str) -> None:
    context = BusinessContextService(session).get_or_create(company_id)
    config = dict(context.configuration or {})
    agents = dict(config.get("agents") or {})
    agents["directeur_log"] = [*(agents.get("directeur_log") or []), {"at": service.now().isoformat(), "text": text[:600]}][-JOURNAL_KEEP:]
    config["agents"] = agents
    context.configuration = config
    session.add(context)
    session.commit()


def _rules(session: Session, company: Company, state: dict) -> tuple[list[str], int]:
    """What the Directeur does without a language model: questions, and a nudge to the agents."""

    done: list[str] = []
    asked = followup.ask_questions(session, company)
    if asked:
        done.append(f"{asked} question(s) posée(s) pour combler ce qui me manque")
    config = config_service.get_configuration(session, company.id)
    answers = config.get("answers") or {}
    if not any(answers.get(k) for k in ("goals",)) and followup.ask(session, company, "directeur", "goal:90d", "Quel est votre objectif numéro 1 pour les 3 prochains mois (chiffre d'affaires, marge, nouveaux clients, trésorerie…) ?",
                                                                   "Je règle mes priorités et celles des autres agents sur ce que vous visez vraiment."):
        done.append("question sur votre objectif des 3 prochains mois")
    if state["counts"]["transactions"] and followup.ask(session, company, "directeur", "pain:biggest", "Quel est aujourd'hui votre plus gros souci dans l'entreprise (marges, retards fournisseurs, clients qui partent, trésorerie, temps perdu) ?",
                                                        "Pour que le Veilleur et l'Analyste cherchent d'abord ce qui vous fait mal."):
        done.append("question sur votre plus gros souci")
    if state["unfinished"]:
        done.append(f"rappel de {len(state['unfinished'])} tâche(s) non terminée(s)")
    session.commit()
    return done, asked


def _initiatives(session: Session, company: Company, state: dict) -> tuple[str | None, int]:
    if not veilleur_agent.enabled():
        return None, 0
    try:
        raw = perplexity.chat(_SYSTEM, json.dumps(state, ensure_ascii=False))
        match = re.search(r"\{.*\}", raw, re.S)
        data = json.loads(match.group(0)) if match else {}
    except (perplexity.PerplexityError, ValueError):
        return None, 0
    created = 0
    for t in (data.get("initiatives") or [])[:MAX_INITIATIVES]:
        if not isinstance(t, dict) or not str(t.get("title") or "").strip():
            continue
        action = t.get("action") if t.get("action") in ("task", "browser") else "none"
        item = {"category": "initiative", "title": t["title"], "summary": t.get("summary"), "why_it_matters": t.get("why") or "Initiative du Directeur", "suggested_action": {"type": action, "text": t.get("text") or t["title"]}}
        created += service._ingest(session, company, item, [], agent="directeur")
    question = str(data.get("question") or "").strip()
    if question and question.lower() not in ("null", "none", "non"):
        followup.ask(session, company, "directeur", f"dir:{question.lower()[:80]}", question, "Question du Directeur pour mieux piloter votre entreprise.")
    session.commit()
    return (str(data.get("message") or "").strip() or None), created


def run_directeur(session: Session, company: Company) -> dict:
    progress.start(company.id, "directeur", "Le Directeur fait le point sur l'entreprise")
    try:
        state = _state(session, company)
        progress.step(company.id, "directeur", "Il passe en revue l'activité de chaque agent", 20)
        done, _ = _rules(session, company, state)
        progress.step(company.id, "directeur", "Il réfléchit aux initiatives à prendre", 55)
        message, created = _initiatives(session, company, state)
        if created:
            done.append(f"{created} initiative(s) proposée(s)")
        text = message or ("Le point est fait : " + ("; ".join(done) if done else "rien à ajouter pour l'instant, les agents suivent leur cours") + ".")
        if message and done:
            text += " Cette fois : " + "; ".join(done) + "."
        _write(session, company.id, text)
        service.log_run(session, company.id, "directeur", "ok", text[:300], created)
        progress.finish(company.id, "directeur", "done", text[:200])
        return {"message": text, "done": done}
    except Exception:
        session.rollback()
        progress.finish(company.id, "directeur", "error", "Le Directeur n'a pas pu finir son tour.")
        raise
