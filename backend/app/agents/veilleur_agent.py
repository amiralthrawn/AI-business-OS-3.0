"""The Veilleur as a real generative agent.

A language model with tools, in a loop: it searches the web, reads the pages
it is pointed at, asks the Analyste what the company's own data says, and
records what is worth keeping. Nothing it saves can cite a source it did not
actually see, and a page it cannot read is reported as unreadable.
"""

import ipaddress
import json
import re
import socket
from datetime import date
from urllib.parse import urlparse

import httpx
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.agents import perplexity
from app.config import get_settings
from app.core.entities import Customer, Product, StockPosition, Supplier

MAX_STEPS = 9
PAGE_CHARS = 12000

SYSTEM = (
    "Tu es le Veilleur : l'agent de veille et de recherche d'une PME française, dans son logiciel de pilotage. "
    "Tu réponds comme un assistant généraliste puissant, en français, avec des faits. "
    "Tes outils : web_search (recherche web avec sources), read_page (lire une page web précise, par exemple un site que le client te donne), "
    "ask_analyste (l'Analyste connaît les données déjà intégrées dans le logiciel : produits, stocks, fournisseurs, clients), save_finding (enregistrer une information utile et sourcée). "
    "Méthode : comprends l'objectif du client ; si la demande touche ses produits, fournisseurs ou clients, interroge d'abord l'Analyste pour savoir quelles données comparer ; "
    "lis les sites indiqués ; recoupe avec une recherche web ; enregistre chaque information utile avec save_finding (une par sujet, avec ses sources). "
    "Règles : n'invente jamais un chiffre, un prix, un nom ou une date ; si une page est illisible (connexion, JavaScript, blocage), dis-le et cherche une autre voie ; "
    "n'indique comme source que des adresses que tu as réellement consultées ; si tu ne trouves rien de fiable, explique précisément ce que tu as essayé. "
    "Termine par une réponse claire : ce que tu as trouvé, ce que tu as enregistré, ce qui manque et la suite que tu proposes."
)

TOOLS = [
    {"type": "function", "function": {"name": "web_search", "description": "Recherche sur le web, renvoie une synthèse et les sources.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "read_page", "description": "Lit le texte d'une page web publique (URL complète).", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {"name": "ask_analyste", "description": "Interroge l'Analyste sur les données de l'entreprise déjà dans le logiciel. Donne des mots-clés (référence, marque, famille de produit, nom de fournisseur ou de client) ou laisse vide pour un aperçu général.", "parameters": {"type": "object", "properties": {"terms": {"type": "array", "items": {"type": "string"}}}}}},
    {"type": "function", "function": {"name": "save_finding", "description": "Enregistre une information utile pour l'entreprise (elle sera proposée au client). Sources = adresses consultées.", "parameters": {"type": "object", "properties": {
        "title": {"type": "string"}, "summary": {"type": "string"}, "why_it_matters": {"type": "string"}, "category": {"type": "string"},
        "date": {"type": "string", "description": "AAAA-MM-JJ si c'est un événement daté"}, "sources": {"type": "array", "items": {"type": "string"}},
        "suggested_action": {"type": "object", "properties": {"type": {"type": "string", "enum": ["calendar_event", "task", "none"]}, "text": {"type": "string"}}},
    }, "required": ["title", "summary", "why_it_matters", "sources"]}}},
]


def enabled() -> bool:
    return bool((get_settings().openrouter_api_key or "").strip())


# --- tools --------------------------------------------------------------------

def _public_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


def _text_of(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|noscript|svg|head)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?i)</(p|div|tr|li|h\d|table|br)>|<br\s*/?>", "\n", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")):
        html = html.replace(a, b)
    lines = (re.sub(r"[ \t]+", " ", line).strip() for line in html.splitlines())
    return "\n".join(line for line in lines if line)


def read_page(url: str) -> tuple[str, str | None]:
    """(text for the model, url actually read or None)."""

    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return "Adresse invalide : il faut une URL complète commençant par http(s)://", None
    if not _public_host(parsed.hostname):
        return "Cette adresse n'est pas une page publique : lecture refusée.", None
    try:
        res = httpx.get(url.strip(), timeout=20, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (compatible; VeilleurBot/1.0)", "Accept-Language": "fr,en;q=0.8"})
    except httpx.HTTPError as exc:
        return f"Page injoignable : {str(exc)[:200]}", None
    if res.status_code != 200:
        return f"La page a répondu {res.status_code} (accès refusé ou inexistante).", None
    if "html" not in res.headers.get("content-type", "") and "text" not in res.headers.get("content-type", ""):
        return "Ce n'est pas une page de texte lisible.", None
    text = _text_of(res.text[:1_500_000])
    if len(text) < 200:
        return "La page est presque vide pour un lecteur automatique (contenu chargé par JavaScript ou protégé). Impossible d'en extraire des données fiables.", str(res.url)
    return text[:PAGE_CHARS], str(res.url)


def analyste_digest(session: Session, company_id, terms: list[str]) -> str:
    """What the company's data says, computed (the Analyste uses no language model)."""

    products = session.query(func.count(Product.id)).filter_by(company_id=company_id).scalar() or 0
    suppliers = session.query(func.count(Supplier.id)).filter_by(company_id=company_id).scalar() or 0
    customers = session.query(func.count(Customer.id)).filter_by(company_id=company_id).scalar() or 0
    lines = [f"Données du logiciel : {products} produits, {suppliers} fournisseurs, {customers} clients/prospects."]
    top = (
        session.query(Product.name, Product.sku, Product.brand, func.sum(StockPosition.quantity))
        .join(StockPosition, StockPosition.product_id == Product.id).filter(Product.company_id == company_id)
        .group_by(Product.id).order_by(func.sum(StockPosition.quantity).desc()).limit(8).all()
    )
    if top:
        lines.append("Plus gros stocks : " + "; ".join(f"{n} ({s or 'sans réf.'}, {b or '?'}) : {int(q or 0)}" for n, s, b, q in top))
    brands = session.query(Product.brand, func.count(Product.id)).filter(Product.company_id == company_id, Product.brand.isnot(None)).group_by(Product.brand).order_by(func.count(Product.id).desc()).limit(8).all()
    if brands:
        lines.append("Marques les plus présentes : " + ", ".join(f"{b} ({c})" for b, c in brands))
    for term in [t.strip() for t in terms if t and t.strip()][:5]:
        like = f"%{term}%"
        found = session.query(Product).filter(Product.company_id == company_id, or_(Product.name.ilike(like), Product.sku.ilike(like), Product.brand.ilike(like), Product.category.ilike(like))).limit(6).all()
        sup = session.query(Supplier.name, Supplier.country).filter(Supplier.company_id == company_id, Supplier.name.ilike(like)).limit(4).all()
        cus = session.query(Customer.name, Customer.status).filter(Customer.company_id == company_id, Customer.name.ilike(like)).limit(4).all()
        lines.append(f"« {term} » : " + ("; ".join(f"produit {p.name} ({p.sku or '—'}, coût {p.unit_cost if p.unit_cost is not None else '?'}, prix de vente {p.sale_price if p.sale_price is not None else '?'})" for p in found) or "aucun produit")
                     + (" | fournisseurs : " + ", ".join(f"{n} ({c or '?'})" for n, c in sup) if sup else "") + (" | clients : " + ", ".join(f"{n} ({s})" for n, s in cus) if cus else ""))
    from app.agents import service

    last = service.last_analysis(session, company_id)
    if last:
        lines.append(f"Dernière analyse de l'Analyste : {last['summary']}")
    return "\n".join(lines)


# --- the loop -------------------------------------------------------------------

def _chat(messages: list[dict]) -> dict:
    settings = get_settings()
    body = {"model": settings.openrouter_agent_model, "temperature": 0.2, "messages": messages, "tools": TOOLS}
    try:
        res = httpx.post(perplexity.OPENROUTER_URL, headers={"Authorization": f"Bearer {settings.openrouter_api_key.strip()}", "Content-Type": "application/json"}, json=body, timeout=120)
    except httpx.HTTPError as exc:
        raise perplexity.PerplexityError(f"OpenRouter unreachable: {exc}") from exc
    if res.status_code != 200:
        raise perplexity.PerplexityError(f"OpenRouter answered {res.status_code}: {res.text[:600]}")
    try:
        data = res.json()
        message = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise perplexity.PerplexityError("Unexpected OpenRouter answer") from exc
    perplexity._record(settings.openrouter_agent_model, data.get("usage"))
    return message


def run(session: Session, company, profile: str, request: str, save) -> dict:
    """`save(item, sources) -> bool` stores a finding. Returns {answer, found}."""

    seen: set[str] = set()
    found: list[dict] = []
    messages: list[dict] = [
        {"role": "system", "content": f"{SYSTEM}\n\nDate du jour : {date.today().isoformat()}.\nProfil du client : {profile}"},
        {"role": "user", "content": request},
    ]
    answer = ""
    for _ in range(MAX_STEPS):
        message = _chat(messages)
        calls = message.get("tool_calls") or []
        messages.append({"role": "assistant", "content": message.get("content") or "", **({"tool_calls": calls} if calls else {})})
        if not calls:
            answer = (message.get("content") or "").strip()
            break
        for call in calls:
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
            except ValueError:
                args = {}
            result = _tool(session, company, name, args, seen, found, save)
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": result[:PAGE_CHARS + 500]})
    if not answer:
        messages.append({"role": "user", "content": "Conclus maintenant : réponds au client avec ce que tu as trouvé et enregistré."})
        answer = _final(messages)
    return {"answer": answer, "found": found}


def _final(messages: list[dict]) -> str:
    settings = get_settings()
    try:
        res = httpx.post(perplexity.OPENROUTER_URL, headers={"Authorization": f"Bearer {settings.openrouter_api_key.strip()}", "Content-Type": "application/json"}, json={"model": settings.openrouter_agent_model, "temperature": 0.2, "messages": messages}, timeout=120)
        data = res.json()
        perplexity._record(settings.openrouter_agent_model, data.get("usage"))
        return (data["choices"][0]["message"].get("content") or "").strip()
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        return "Je n'ai pas pu conclure la recherche à temps ; ce qui a été enregistré est listé ci-dessous."


def _tool(session, company, name: str, args: dict, seen: set[str], found: list[dict], save) -> str:
    if name == "web_search":
        try:
            text, sources = perplexity.ask("Réponds en français, factuellement, uniquement à partir des sources trouvées. Donne chiffres et noms exacts quand ils existent.", str(args.get("query", ""))[:500])
        except perplexity.PerplexityError as exc:
            return f"Recherche indisponible : {str(exc)[:200]}"
        seen.update(sources)
        return text + ("\nSources : " + ", ".join(sources[:8]) if sources else "\n(aucune source trouvée)")
    if name == "read_page":
        text, url = read_page(str(args.get("url", "")))
        if url:
            seen.add(url)
            seen.add(str(args.get("url", "")).strip())
        return text
    if name == "ask_analyste":
        terms = args.get("terms") if isinstance(args.get("terms"), list) else []
        return analyste_digest(session, company.id, [str(t) for t in terms])
    if name == "save_finding":
        sources = [s for s in (args.get("sources") or []) if isinstance(s, str) and s in seen]
        if not sources:
            return "Refusé : aucune des sources citées n'a été consultée. Consulte la page (read_page) ou fais une recherche, puis cite ces adresses."
        item = {k: args.get(k) for k in ("title", "summary", "why_it_matters", "category", "date", "suggested_action")}
        if not str(item.get("title") or "").strip():
            return "Refusé : titre manquant."
        created = save(item, sources)
        if created:
            found.append({"title": str(item["title"])[:255], "summary": str(item.get("summary") or "")[:600], "why": str(item.get("why_it_matters") or "")[:400], "sources": sources[:5]})
        return "Enregistré." if created else "Déjà enregistré auparavant."
    return "Outil inconnu."
