"""The connection guide: an agent that looks up, for each tool a company
declared, how to get its data out, and helps through the sync.

Honesty rules (decided with the product owner):
- Steps are shown only when the web search returned real sources for them.
  Without sources the agent says it found nothing and falls back to the
  generic, clearly labelled, category instructions. It never invents a menu.
- It acts only inside the sync (suggest the next file, request a connection,
  put a reminder in the calendar); nothing leaves the company.
"""

import re
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.agents import perplexity
from app.business_context.service import BusinessContextService
from app.configuration import tools

KIND_LABEL = {
    "fec": "écritures comptables (FEC)",
    "customers": "clients",
    "suppliers": "fournisseurs",
    "products": "produits",
    "sales": "ventes",
    "purchases": "achats",
}
MAX_QUESTION = 600

_RESEARCH_SYSTEM = (
    "Tu aides une PME française à exporter ses données depuis un logiciel. "
    "Réponds UNIQUEMENT à partir de la documentation officielle ou d'articles d'aide que tu trouves. "
    "N'invente jamais un menu, un bouton ou une option. "
    "Si tu ne trouves aucune procédure documentée, réponds exactement : NON_TROUVE. "
    "Sinon réponds par une liste numérotée de 3 à 7 étapes, une par ligne, au format « 1. Titre court : une phrase simple pour un non-technicien ». "
    "Puis, sur une dernière ligne qui commence par « À savoir : », les limites éventuelles (version, droits d'administrateur). Rien d'autre."
)

_ASK_SYSTEM = (
    "Tu es l'assistant de connexion d'une PME française qui configure un logiciel de pilotage. "
    "Réponds en français, simplement, en quelques phrases, uniquement à partir de la documentation que tu trouves pour le logiciel demandé. "
    "Si tu ne trouves pas l'information, dis-le clairement plutôt que de deviner."
)


class GuideError(RuntimeError):
    pass


def _label_and_category(tool_key: str) -> tuple[str, tools.Category]:
    info = tools.tool_info(tool_key)
    if info is None:
        raise KeyError(tool_key)
    return info


_STEP = re.compile(r"^\s*(\d+)[.)]\s+(.+)$")


def _plain(text: str) -> str:
    return re.sub(r"[*_`#]+", "", text).strip()


def _parse_steps(text: str) -> tuple[list[dict], str]:
    """Numbered lines -> steps; a trailing 'À savoir :' line -> caveats."""

    steps: list[dict] = []
    caveats = ""
    for line in text.splitlines():
        line = line.strip()
        if line.lower().lstrip("*_ ").startswith("à savoir"):
            caveats = _plain(line.split(":", 1)[-1])[:400]
            continue
        m = _STEP.match(line)
        if not m:
            continue
        body = _plain(m.group(2))
        title, sep, detail = body.partition(":")
        if not sep:
            title, detail = "", body
        steps.append({"title": title.strip()[:120], "detail": detail.strip()[:400]})
    return steps[:7], caveats


def _generic(tool_key: str) -> str:
    _, category = _label_and_category(tool_key)
    return tools.KNOWN_EXPORTS.get(tool_key, category.export)


def _clean_steps(raw: object) -> list[dict]:
    steps: list[dict] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        title, detail = str(item.get("title") or "").strip(), str(item.get("detail") or "").strip()
        if title or detail:
            steps.append({"title": title[:120], "detail": detail[:400]})
    return steps[:7]


def _store(session: Session, company_id: uuid.UUID, tool_key: str, guide: dict) -> None:
    context = BusinessContextService(session).get_or_create(company_id)
    config = dict(context.configuration or {})
    guides = dict(config.get("tool_guides") or {})
    guides[tool_key] = guide
    config["tool_guides"] = guides
    context.configuration = config
    session.add(context)
    session.commit()


def get_guide(session: Session, company_id: uuid.UUID, tool_key: str, *, refresh: bool = False) -> dict:
    """Cached per tool. status: sourced | no_sources | unavailable."""

    label, category = _label_and_category(tool_key)
    config = dict(BusinessContextService(session).get_or_create(company_id).configuration or {})
    cached = (config.get("tool_guides") or {}).get(tool_key)
    if cached and not refresh and cached.get("status") != "unavailable":
        return {**cached, "generic": _generic(tool_key)}

    base = {"tool": tool_key, "label": label, "generic": _generic(tool_key), "researched_at": datetime.now(timezone.utc).isoformat()}
    if not perplexity.configured():
        return {**base, "status": "unavailable", "reason": "not_configured", "steps": [], "sources": [], "caveats": ""}

    wanted = ", ".join(KIND_LABEL[k] for k in category.import_kinds) or "ses relevés"
    question = (
        f"Comment exporter depuis le logiciel « {label} » ({category.label}) en CSV ou Excel : {wanted} ? "
        "Donne la procédure exacte telle que documentée, et dis si le logiciel permet aussi un export automatique ou une API."
    )
    try:
        text, sources = perplexity.ask(_RESEARCH_SYSTEM, question)
    except perplexity.PerplexityError as exc:
        return {**base, "status": "unavailable", "reason": str(exc)[:900], "steps": [], "sources": [], "caveats": ""}
    if "NON_TROUVE" in text:
        steps, caveats, why = [], "", "La recherche n'a trouvé aucune procédure documentée."
    else:
        steps, caveats = _parse_steps(text)
        why = ""
        if len(steps) < 2:
            steps, why = [], "La réponse trouvée n'était pas une procédure exploitable."
    if steps and not sources:
        steps, why = [], "Une procédure a été proposée mais sans aucune source : je ne l'affiche pas."
    guide = {
        **base,
        "status": "sourced" if steps else "no_sources",
        "steps": steps,
        "sources": sources[:6] if steps else [],
        "caveats": caveats if steps else "",
        "reason": why,
    }
    _store(session, company_id, tool_key, {k: v for k, v in guide.items() if k != "generic"})
    _log(session, company_id, "ok" if steps else "no_sources", f"Procédure de {label} : {len(steps)} étape(s) sourcée(s)" if steps else f"Procédure de {label} : rien de fiable trouvé", len(steps))
    return guide


def _log(session: Session, company_id: uuid.UUID, status: str, message: str, found: int = 0) -> None:
    from app.agents import service as agents_service

    agents_service.log_run(session, company_id, "guide", status, message, found)


def ask(session: Session, company_id: uuid.UUID, tool_key: str, question: str) -> dict:
    label, category = _label_and_category(tool_key)
    question = question.strip()[:MAX_QUESTION]
    if not perplexity.configured():
        return {"answer": "Je ne peux pas chercher sur le web pour le moment (recherche non configurée). Utilisez les instructions générales de la page.", "sources": [], "grounded": False}
    from app.agents import service as agents_service

    past = agents_service.recall(session, company_id, "guide", n=4, only=label)
    system = _ASK_SYSTEM + (f"\nÉchanges précédents avec ce client sur ce logiciel (n'y reviens pas, complète) :\n{past}" if past else "")
    try:
        text, sources = perplexity.ask(system, f"Logiciel : {label} ({category.label}).\nQuestion du client : {question}")
    except perplexity.PerplexityError:
        return {"answer": "La recherche est momentanément indisponible. Réessayez dans un instant.", "sources": [], "grounded": False}
    if not sources:
        return {"answer": "Je n'ai trouvé aucune source fiable pour répondre à cette question, donc je préfère ne pas deviner. Voulez-vous que nous vous aidions directement ?", "sources": [], "grounded": False}
    used = agents_service.used_summary(perplexity.peek_usage())
    agents_service.remember(session, company_id, "guide", f"{label} : {question}", text)
    _log(session, company_id, "ok", f"Question sur {label} : {question[:100]}", 1)
    return {"answer": text.strip()[:1500], "sources": sources[:5], "grounded": True, "used": used}


def next_steps(config: dict, tool_key: str) -> dict:
    """What the agent proposes after reading what has been imported for this
    tool. Deterministic: every statement comes from the recorded imports."""

    label, category = _label_and_category(tool_key)
    mine = [i for i in (config.get("imports") or []) if i.get("tool") == tool_key]
    got = {i["kind"] for i in mine}
    state = (config.get("tools") or {}).get(tool_key) or {}
    suggestions: list[dict] = []
    notes: list[str] = []

    for entry in mine[-3:]:
        total = entry.get("created", 0) + entry.get("updated", 0) + entry.get("skipped", 0)
        if total and entry.get("skipped", 0) / total > 0.3:
            notes.append(f"{entry.get('file', 'Un fichier')} : {entry['skipped']} lignes sur {total} n'ont pas pu être lues. Vérifiez que l'export contient bien les colonnes d'origine.")
    for kind in category.import_kinds:
        if kind not in got:
            suggestions.append({"action": "upload", "kind": kind, "text": f"Ajouter vos {KIND_LABEL[kind]} depuis {label}"})
    if got and state.get("connection") != "requested":
        suggestions.append({"action": "request_connection", "text": f"Faire connecter {label} pour qu'il se mette à jour sans fichier"})
    if got:
        suggestions.append({"action": "reminder", "text": f"Me rappeler de refaire l'export de {label} dans 30 jours"})
    return {"imported_kinds": sorted(got), "notes": notes, "suggestions": suggestions}


def add_reminder(session: Session, company_id: uuid.UUID, tool_key: str, user_id: uuid.UUID | None) -> dict:
    from app.core.entities import CalendarEvent

    label, _ = _label_and_category(tool_key)
    when = (datetime.now(timezone.utc) + timedelta(days=30)).replace(hour=9, minute=0, second=0, microsecond=0)
    event = CalendarEvent(
        company_id=company_id, title=f"Refaire l'export de {label}", kind="deadline", starts_at=when, all_day=True,
        notes="Rappel de l'assistant de connexion : déposez un export à jour pour garder vos décisions fiables.", created_by=user_id,
    )
    session.add(event)
    session.commit()
    return {"id": str(event.id), "starts_at": when.isoformat()}
