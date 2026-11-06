"""The Veilleur: watches the outside world for anything that may matter to
THIS company and turns it into proposals. No closed list of topics.

Two passes, both through Perplexity:
1. the outside world (market, events, prices, competitors, regulation,
   calendar -- holidays, fairs, deadlines);
2. the company itself (its Google Maps rating, its visibility on the web).

Every item must be verifiable and carry a source; nothing is invented. When
the Veilleur cannot treat what it found without an internal fact, it says so
(`needs_info`) and the guide asks the company for it.
"""

import json
import re
from datetime import date, datetime, timezone

from app.agents import perplexity

SYSTEM = (
    "Tu es le Veilleur d'une entreprise française, un agent de veille. Tu réponds UNIQUEMENT par un tableau JSON valide, "
    "sans texte autour. Chaque élément doit être réel et vérifiable sur le web : n'invente jamais une information, une date, "
    "un chiffre ou une source. S'il n'y a rien de sûr, réponds []. Format de chaque élément : "
    '{"category": "marché|événement|prix|concurrent|réglementation|calendrier|réputation|visibilité|autre", '
    '"title": "phrase courte", "summary": "2 phrases maximum, faits précis", '
    '"why_it_matters": "pourquoi cela compte pour CETTE entreprise", '
    '"date": "AAAA-MM-JJ ou null (date de l\'événement ou de l\'échéance)", '
    '"suggested_action": {"type": "calendar_event|task|none", "text": "action concrète proposée"}, '
    '"needs_info": "information interne qui te manque pour traiter cet élément, sinon null"}'
)


def profile_text(company_name: str, website: str | None, profile: dict, knowledge: list[dict]) -> str:
    parts = [f"Entreprise : {company_name}."]
    if website:
        parts.append(f"Site web : {website}.")
    if profile.get("sector_label"):
        parts.append(f"Secteur : {profile['sector_label']}.")
    for key, label in (("goals", "Objectifs"), ("problems", "Difficultés"), ("externals", "Facteurs externes qui comptent")):
        values = (profile.get("answers") or {}).get(key) or []
        if values:
            parts.append(f"{label} : {', '.join(values)}.")
    notes = " ".join(v for v in (profile.get("answer_notes") or {}).values() if v)
    if notes:
        parts.append(f"Précisions : {notes}")
    if profile.get("problems"):
        parts.append(f"Problèmes déclarés : {profile['problems']}")
    tools = [t["label"] for t in profile.get("tools", [])][:12]
    if tools:
        parts.append(f"Outils utilisés : {', '.join(tools)}.")
    if knowledge:
        parts.append("Informations données par l'entreprise : " + " ".join(f"{k['question']} -> {k['answer']}" for k in knowledge[-8:]))
    return " ".join(parts)


def outside_prompt(profile: str, today: date) -> str:
    return (
        f"Nous sommes le {today.isoformat()}. {profile}\n\n"
        "Cherche sur le web TOUT ce qui est susceptible d'intéresser cette entreprise, sans te limiter à une liste de sujets : "
        "marché et tendances, événements et salons à venir (dates et lieux exacts), prix et cours qui bougent, concurrents, "
        "réglementation et échéances légales, jours fériés ou fêtes à venir utiles pour sa relation client ou ses équipes, "
        "actualité de ses clients et fournisseurs types. Privilégie ce qui est daté dans les 90 prochains jours ou très récent. "
        "Retourne au plus 8 éléments, les plus utiles d'abord."
    )


def self_prompt(profile: str, name: str, today: date) -> str:
    return (
        f"Nous sommes le {today.isoformat()}. {profile}\n\n"
        f"Recherche ce que le web dit de l'entreprise « {name} » elle-même : sa note et ses avis Google Maps, sa visibilité "
        "sur internet (résultats de recherche, site, réseaux), sa réputation. Si tu ne trouves pas l'entreprise avec certitude, "
        "réponds [] ou un seul élément avec needs_info pour demander son adresse ou son site. Pour chaque point faible réel, "
        "propose des actions concrètes. Au plus 4 éléments."
    )


def topics_prompt(profile: str, topics: list[str], today: date) -> str:
    listed = "\n".join(f"- {t}" for t in topics)
    return (
        f"Nous sommes le {today.isoformat()}. {profile}\n\n"
        "L'entreprise demande EXPRESSÉMENT de suivre les sujets suivants (ce peut être des sites, des concurrents, des salons, des marchés) :\n"
        f"{listed}\n\n"
        "Pour chacun, cherche sur le web tout ce que tu peux établir de fiable : ce que c'est, ce que cela change pour cette entreprise, "
        "les prix, stocks, dates, lieux ou chiffres publics, et comment obtenir l'information qui manque (par exemple une liste d'exposants). "
        "Distingue clairement ce qui est vérifié de ce que tu n'as pas pu confirmer (dans ce cas, n'écris pas de fait, mets-le dans needs_info). "
        "Un élément par information utile, au plus 3 par sujet."
    )


def parse_items(text: str) -> list[dict]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    return [d for d in data if isinstance(d, dict) and str(d.get("title") or "").strip()]


def parse_date(value) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        d = date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def scan(profile: str, company_name: str, today: date, topics: list[str] | None = None) -> list[tuple[dict, list[str]]]:
    """Returns [(item, source_urls)]. Raises perplexity.PerplexityError."""

    out: list[tuple[dict, list[str]]] = []
    prompts = [outside_prompt(profile, today), self_prompt(profile, company_name, today)]
    if topics:
        prompts.append(topics_prompt(profile, topics[:12], today))
    for prompt in prompts:
        text, sources = perplexity.ask(SYSTEM, prompt)
        out.extend((item, sources) for item in parse_items(text))
    return out
