"""The Exécutant: the agent that does the work.

Given a task (an accepted proposal, or a direct request) it acts inside the
company's own software with a short list of tools: complete the catalogue,
supplier and customer files, the calendar, tasks, e-mail DRAFTS, and the
web / site for the facts it needs. Everything it creates is recorded, so each
step can be undone. It never sends anything outside the company.
"""

import json
import uuid
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.agents import perplexity, veilleur_agent
from app.core.entities import CalendarEvent, Communication, Company, Customer, Product, Supplier, Task

MAX_STEPS = 10

SYSTEM = (
    "Tu es l'Exécutant : l'agent qui fait réellement le travail dans le logiciel d'une PME française. On te donne une tâche ; tu la réalises avec tes outils, puis tu rends compte. "
    "Outils : find_in_company_data (ce que le logiciel sait déjà : produits, stocks, fournisseurs, clients, analyse), web_search et read_page (faits externes), "
    "create_product, create_supplier, create_customer, create_calendar_event, create_task, draft_email (brouillon : RIEN n'est envoyé, le client relit et envoie). "
    "Règles : vérifie d'abord avec find_in_company_data pour ne pas créer de doublon ; n'invente aucune donnée (référence, prix, adresse e-mail, date) : si une information manque, ne crée pas l'élément et dis précisément ce qu'il faut fournir ; "
    "ne crée que ce que la tâche demande ; n'écris jamais à un tiers. Termine par un compte rendu court : ce que tu as fait (avec les noms), ce que tu n'as pas pu faire et pourquoi, la suite proposée."
)

_P = lambda **props: {"type": "object", "properties": props}
TOOLS = [
    {"type": "function", "function": {"name": "find_in_company_data", "description": "Cherche dans les données du logiciel par mots-clés (référence, marque, nom de fournisseur ou de client).", "parameters": _P(terms={"type": "array", "items": {"type": "string"}})}},
    {"type": "function", "function": {"name": "web_search", "description": "Recherche web avec sources.", "parameters": {**_P(query={"type": "string"}), "required": ["query"]}}},
    {"type": "function", "function": {"name": "read_page", "description": "Lit une page web publique.", "parameters": {**_P(url={"type": "string"}), "required": ["url"]}}},
    {"type": "function", "function": {"name": "create_product", "description": "Ajoute un produit au catalogue.", "parameters": {**_P(name={"type": "string"}, sku={"type": "string"}, brand={"type": "string"}, category={"type": "string"}, unit_cost={"type": "number"}, sale_price={"type": "number"}), "required": ["name"]}}},
    {"type": "function", "function": {"name": "create_supplier", "description": "Ajoute un fournisseur.", "parameters": {**_P(name={"type": "string"}, country={"type": "string"}), "required": ["name"]}}},
    {"type": "function", "function": {"name": "create_customer", "description": "Ajoute un client ou prospect.", "parameters": {**_P(name={"type": "string"}, country={"type": "string"}, notes={"type": "string"}, status={"type": "string", "enum": ["prospect", "active"]}), "required": ["name"]}}},
    {"type": "function", "function": {"name": "create_calendar_event", "description": "Ajoute un événement au calendrier (date AAAA-MM-JJ).", "parameters": {**_P(title={"type": "string"}, date={"type": "string"}, notes={"type": "string"}), "required": ["title", "date"]}}},
    {"type": "function", "function": {"name": "create_task", "description": "Crée une tâche de suivi pour l'équipe.", "parameters": {**_P(title={"type": "string"}, description={"type": "string"}), "required": ["title"]}}},
    {"type": "function", "function": {"name": "draft_email", "description": "Prépare un brouillon d'e-mail (non envoyé).", "parameters": {**_P(to={"type": "string"}, subject={"type": "string"}, body={"type": "string"}), "required": ["subject", "body"]}}},
]


def _s(value: object, n: int) -> str:
    return " ".join(str(value or "").split())[:n]


def _num(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _tool(session: Session, company: Company, name: str, args: dict, done: list[dict], seen: set[str]) -> str:
    cid = company.id

    def record(kind: str, obj, label: str) -> str:
        session.add(obj)
        session.flush()
        done.append({"kind": kind, "id": str(obj.id), "label": label})
        return f"Créé : {label}."

    if name == "find_in_company_data":
        terms = args.get("terms") if isinstance(args.get("terms"), list) else []
        return veilleur_agent.analyste_digest(session, cid, [str(t) for t in terms])
    if name in ("web_search", "read_page"):
        return veilleur_agent._tool(session, company, name, args, seen, [], lambda *_: False)
    if name == "create_product":
        title = _s(args.get("name"), 255)
        if not title:
            return "Refusé : nom manquant."
        sku = _s(args.get("sku"), 120) or None
        existing = session.query(Product).filter(Product.company_id == cid)
        if (sku and existing.filter(Product.sku == sku).first()) or existing.filter(Product.name == title).first():
            return "Déjà dans le catalogue : rien créé."
        return record("product", Product(company_id=cid, name=title, sku=sku, brand=_s(args.get("brand"), 120) or None, category=_s(args.get("category"), 120) or None, unit_cost=_num(args.get("unit_cost")), sale_price=_num(args.get("sale_price"))), f"produit {title}")
    if name == "create_supplier":
        title = _s(args.get("name"), 255)
        if not title or session.query(Supplier).filter(Supplier.company_id == cid, Supplier.name == title).first():
            return "Refusé ou déjà existant : rien créé."
        return record("supplier", Supplier(company_id=cid, name=title, country=_s(args.get("country"), 120) or None, certifications=[]), f"fournisseur {title}")
    if name == "create_customer":
        title = _s(args.get("name"), 255)
        if not title or session.query(Customer).filter(Customer.company_id == cid, Customer.name == title).first():
            return "Refusé ou déjà existant : rien créé."
        status = args.get("status") if args.get("status") in ("prospect", "active") else "prospect"
        return record("customer", Customer(company_id=cid, name=title, country=_s(args.get("country"), 120) or None, notes=_s(args.get("notes"), 2000) or None, status=status), f"{'prospect' if status == 'prospect' else 'client'} {title}")
    if name == "create_calendar_event":
        try:
            when = datetime.combine(date.fromisoformat(str(args.get("date"))[:10]), datetime.min.time(), tzinfo=timezone.utc)
        except ValueError:
            return "Refusé : date invalide (format AAAA-MM-JJ)."
        title = _s(args.get("title"), 200)
        return record("calendar_event", CalendarEvent(company_id=cid, title=title, kind="other", starts_at=when, all_day=True, notes=_s(args.get("notes"), 2000) or None, source="executant"), f"événement « {title} » le {when.date().isoformat()}")
    if name == "create_task":
        from app.actions.service import ActionsService
        from app.core.events.tenant import TenantEventBus
        from app.event_bus import event_bus

        title = _s(args.get("title"), 255)
        task = ActionsService(session, TenantEventBus(event_bus, cid)).create_manual_task(company_id=cid, title=title, description=_s(args.get("description"), 2000))
        done.append({"kind": "task", "id": str(task.id), "label": f"tâche « {title} »"})
        return f"Créé : tâche « {title} »."
    if name == "draft_email":
        from app.core.entities.communication import CommunicationDirection

        subject = _s(args.get("subject"), 255)
        draft = Communication(company_id=cid, channel="email", direction=CommunicationDirection.OUTBOUND, status="draft", subject=subject, body=str(args.get("body") or "")[:8000], occurred_at=datetime.now(timezone.utc), to_address=_s(args.get("to"), 255) or None, source="ai_draft")
        return record("draft", draft, f"brouillon d'e-mail « {subject} » (non envoyé)")
    return "Outil inconnu."


def run(session: Session, company: Company, task: str, profile: str) -> dict:
    """Returns {answer, done}. `done` lists everything created, for the undo."""

    done: list[dict] = []
    seen: set[str] = set()
    messages: list[dict] = [
        {"role": "system", "content": f"{SYSTEM}\n\nDate du jour : {date.today().isoformat()}.\nProfil du client : {profile}"},
        {"role": "user", "content": task},
    ]
    answer = ""
    for _ in range(MAX_STEPS):
        message = veilleur_agent._chat(messages, TOOLS)
        calls = message.get("tool_calls") or []
        messages.append({"role": "assistant", "content": message.get("content") or "", **({"tool_calls": calls} if calls else {})})
        if not calls:
            answer = (message.get("content") or "").strip()
            break
        for call in calls:
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
            except ValueError:
                args = {}
            result = _tool(session, company, call["function"]["name"], args, done, seen)
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": result[:6000]})
    if not answer:
        messages.append({"role": "user", "content": "Conclus maintenant par ton compte rendu."})
        answer = veilleur_agent._final(messages)
    return {"answer": answer, "done": done}


def undo(session: Session, done: list[dict]) -> int:
    from app.core.entities.task import TaskStatus

    models = {"product": Product, "supplier": Supplier, "customer": Customer, "calendar_event": CalendarEvent, "draft": Communication}
    undone = 0
    for item in reversed(done):
        try:
            obj_id = uuid.UUID(item["id"])
        except (KeyError, ValueError):
            continue
        if item["kind"] == "task":
            task = session.get(Task, obj_id)
            if task is not None:
                task.status = TaskStatus.CANCELLED
                undone += 1
        elif item["kind"] in models:
            obj = session.get(models[item["kind"]], obj_id)
            if obj is not None:
                try:
                    with session.begin_nested():
                        session.delete(obj)
                    undone += 1
                except Exception:  # already used elsewhere (linked records): left in place
                    pass
    return undone
