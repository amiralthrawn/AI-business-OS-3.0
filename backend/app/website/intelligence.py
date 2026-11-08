"""Deep reading of the company's own website.

The site is crawled (same domain, robots.txt respected, a few pages), its
texts and facts are extracted, and the Analyste reads it to understand the
business: what is sold, to whom, how it is presented, what could be better
and what could be synchronised with the software. The understanding is stored
and shared with the other agents; improvements become proposals.
"""

import json
import re
import uuid
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy.orm import Session

from app.agents import perplexity
from app.business_context.service import BusinessContextService
from app.core.entities import Company, Product

MAX_PAGES = 14
PAGE_TEXT = 3500
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
PRIORITY = ("produit", "product", "service", "offre", "solution", "boutique", "catalogue", "a-propos", "about", "qui-sommes", "contact", "tarif", "prix", "blog", "actualit", "references", "clients", "faq")
SOCIAL = ("linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com", "youtube.com", "tiktok.com")


class SiteError(RuntimeError):
    def __init__(self, message: str, blocked: bool = False) -> None:
        super().__init__(message)
        self.blocked = blocked


def normalise_url(raw: str) -> str:
    url = raw.strip()
    if not url:
        raise SiteError("Adresse vide.")
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    parsed = urlparse(url)
    if not parsed.hostname or "." not in parsed.hostname:
        raise SiteError("Cette adresse ne ressemble pas à un site web (exemple : www.monentreprise.fr).")
    return url


class _Reader(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.description = ""
        self.headings: list[str] = []
        self.links: list[str] = []
        self.jsonld: list[str] = []
        self.text: list[str] = []
        self._skip = 0
        self._cur: str | None = None
        self._buf = ""
        self._ld = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "noscript", "svg"):
            if tag == "script" and (a.get("type") or "") == "application/ld+json":
                self._ld, self._buf = True, ""
            else:
                self._skip += 1
        elif tag == "meta" and (a.get("name") or a.get("property") or "").lower() in ("description", "og:description") and not self.description:
            self.description = a.get("content") or ""
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag in ("title", "h1", "h2", "h3"):
            self._cur, self._buf = tag, ""

    def handle_endtag(self, tag):
        if tag == "script" and self._ld:
            self.jsonld.append(self._buf)
            self._ld = False
        elif tag in ("script", "style", "noscript", "svg"):
            self._skip = max(0, self._skip - 1)
        if tag == self._cur:
            value = " ".join(self._buf.split())
            if tag == "title":
                self.title = value
            elif value:
                self.headings.append(value)
            self._cur = None

    def handle_data(self, data):
        if self._ld or self._cur:
            self._buf += data
        if not self._skip and not self._ld and data.strip():
            self.text.append(data.strip())


def _fetch(client: httpx.Client, url: str) -> tuple[int, str, str]:
    res = client.get(url)
    ctype = res.headers.get("content-type", "")
    return res.status_code, res.text if ("html" in ctype or "text" in ctype or "xml" in ctype) else "", str(res.url)


def _robots_ok(client: httpx.Client, base: str) -> bool:
    try:
        status, body, _ = _fetch(client, urljoin(base, "/robots.txt"))
    except httpx.HTTPError:
        return True
    if status != 200:
        return True
    applies = False
    for line in body.splitlines():
        key, _, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "user-agent":
            applies = value == "*"
        elif key == "disallow" and applies and value == "/":
            return False
    return True


def crawl(url: str) -> dict:
    """Reads the site. Raises SiteError with the real reason when it cannot."""

    base_url = normalise_url(url)
    variants = [base_url]
    host = urlparse(base_url).hostname or ""
    if not host.startswith("www."):
        variants.append(base_url.replace(host, f"www.{host}", 1))
    variants.append(base_url.replace("https://", "http://", 1))
    with httpx.Client(timeout=12.0, follow_redirects=True, headers={"User-Agent": UA, "Accept-Language": "fr,en;q=0.8"}) as client:
        start, attempts = None, []
        for candidate in variants:
            try:
                status, body, final = _fetch(client, candidate)
            except httpx.HTTPError as exc:
                attempts.append(f"{candidate} injoignable ({type(exc).__name__})")
                continue
            if status == 200 and body:
                start = (final, body)
                break
            attempts.append(f"{candidate} : HTTP {status}")
        if start is None:
            blocked = any("HTTP 403" in a or "HTTP 401" in a or "HTTP 429" in a for a in attempts)
            raise SiteError(
                f"Impossible de lire le site ({' ; '.join(attempts) or 'aucune réponse'})."
                + (" Le site (ou son hébergeur) bloque les lectures automatiques." if blocked else ""),
                blocked=blocked,
            )
        base, first_html = start
        netloc = urlparse(base).netloc
        if not _robots_ok(client, base):
            raise SiteError("Le fichier robots.txt du site interdit l'exploration automatique : je ne le lis pas.")
        pages: list[dict] = []
        queue, seen = [(base, first_html)], {base.split("#")[0]}
        emails, phones, social = set(), set(), set()
        schema: list[dict] = []
        while queue and len(pages) < MAX_PAGES:
            page_url, html = queue.pop(0)
            if html is None:
                try:
                    status, html, _ = _fetch(client, page_url)
                except httpx.HTTPError:
                    continue
                if status != 200 or not html:
                    continue
            reader = _Reader()
            reader.feed(html)
            text = " ".join(reader.text)
            emails.update(e for e in re.findall(r"[\w.\-+]+@[\w\-]+\.[\w.\-]+", html) if not e.lower().endswith((".png", ".jpg", ".webp", ".svg")))
            phones.update(p.strip() for p in re.findall(r"(?:\+33|0)\s?[1-9](?:[\s.\-]?\d{2}){4}", text))
            for raw in reader.jsonld:
                try:
                    data = json.loads(raw)
                except ValueError:
                    continue
                for node in data if isinstance(data, list) else [data]:
                    if isinstance(node, dict) and node.get("@type"):
                        schema.append({k: node[k] for k in ("@type", "name", "description", "address", "telephone") if k in node})
            ordered = []
            for href in reader.links:
                absolute = urljoin(page_url, href).split("#")[0]
                parsed = urlparse(absolute)
                if any(s in parsed.netloc for s in SOCIAL):
                    social.add(absolute)
                elif parsed.netloc == netloc and absolute not in seen and parsed.scheme in ("http", "https") and not re.search(r"\.(pdf|jpg|jpeg|png|webp|zip|css|js)$", parsed.path, re.I):
                    seen.add(absolute)
                    ordered.append(absolute)
            ordered.sort(key=lambda u: 0 if any(k in u.lower() for k in PRIORITY) else 1)
            queue.extend((u, None) for u in ordered[:25])
            pages.append({"url": page_url, "title": reader.title, "description": reader.description, "headings": reader.headings[:15], "text": text[:PAGE_TEXT], "words": len(text.split())})
        return {"url": base, "pages": pages, "emails": sorted(emails)[:6], "phones": sorted(phones)[:4], "social": sorted(social)[:8], "schema": schema[:6]}


ANALYSIS_SYSTEM = (
    "Tu es l'Analyste d'un logiciel de pilotage pour PME française. Tu lis le contenu du site web de l'entreprise et tu en tires une compréhension précise de son activité. "
    "N'invente rien : uniquement ce qui est dans le contenu fourni. Réponds UNIQUEMENT par un objet JSON avec ces clés : "
    '"summary" (3 à 5 phrases : ce que fait l\'entreprise, pour qui, comment elle se positionne), '
    '"offer" (liste de 3 à 15 produits, familles ou services réellement présentés), '
    '"audience" (à qui elle s\'adresse), '
    '"strengths" (liste courte), "weaknesses" (liste courte, ce qui manque ou dessert le site : prix, contact, preuves, appel à l\'action, contenu…), '
    '"improvements" (liste de 3 à 6 objets {"title","why","action"} : améliorations concrètes du site, par ordre d\'impact), '
    '"syncs" (liste de 0 à 4 objets {"title","why"} : ce qu\'on pourrait synchroniser entre le site et le logiciel : catalogue, stock, prix, formulaire de contact, e-mails…).'
)


def _json_of(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.S)
    try:
        data = json.loads(match.group(0)) if match else {}
    except ValueError:
        data = {}
    return data if isinstance(data, dict) else {}


def _clean_list(value: object, n: int, keys: tuple[str, ...] = ()) -> list:
    out = []
    for item in value if isinstance(value, list) else []:
        if keys and isinstance(item, dict):
            row = {k: " ".join(str(item.get(k) or "").split())[:300] for k in keys}
            if row[keys[0]]:
                out.append(row)
        elif isinstance(item, str) and item.strip() and not keys:
            out.append(" ".join(item.split())[:200])
    return out[:n]


def understand(company_name: str, site: dict) -> tuple[dict, bool]:
    """(analysis, by_model). Falls back to what the pages literally say."""

    material = "\n\n".join(f"### {p['url']}\nTitre : {p['title']}\nDescription : {p['description']}\nTitres : {' | '.join(p['headings'])}\nTexte : {p['text']}" for p in site["pages"])[:24000]
    facts = f"Contacts trouvés : e-mails {site['emails'] or 'aucun'}, téléphones {site['phones'] or 'aucun'}, réseaux {site['social'] or 'aucun'}."
    if perplexity._openrouter_on():
        try:
            data = _json_of(perplexity.chat(ANALYSIS_SYSTEM, f"Entreprise : {company_name}\n{facts}\n\n{material}"))
            if data.get("summary"):
                return {
                    "summary": " ".join(str(data["summary"]).split())[:1200], "offer": _clean_list(data.get("offer"), 15), "audience": " ".join(str(data.get("audience") or "").split())[:300],
                    "strengths": _clean_list(data.get("strengths"), 6), "weaknesses": _clean_list(data.get("weaknesses"), 6),
                    "improvements": _clean_list(data.get("improvements"), 6, ("title", "why", "action")), "syncs": _clean_list(data.get("syncs"), 4, ("title", "why")),
                }, True
        except perplexity.PerplexityError:
            pass
    home = site["pages"][0] if site["pages"] else {"title": "", "description": "", "headings": []}
    weaknesses = []
    if not site["emails"] and not site["phones"]:
        weaknesses.append("Aucun contact (e-mail ou téléphone) trouvé dans les pages lues")
    if not home["description"]:
        weaknesses.append("Page d'accueil sans description pour les moteurs de recherche")
    return {
        "summary": " ".join(x for x in (home["title"], home["description"]) if x)[:600] or "Contenu du site lu, mais aucune description claire n'a pu en être tirée.",
        "offer": [h for p in site["pages"][:6] for h in p["headings"][:2]][:10], "audience": "", "strengths": [], "weaknesses": weaknesses,
        "improvements": [{"title": w, "why": "Constaté sur le site.", "action": ""} for w in weaknesses], "syncs": [],
    }, False


def research(url: str) -> dict:
    """Fallback when the site blocks automated readers: a sourced web search about it."""

    host = urlparse(normalise_url(url)).hostname or url
    try:
        text, sources = perplexity.ask(
            "Tu décris précisément un site web d'entreprise à partir de ce que tu trouves en ligne (le site lui-même, ses pages produits, annuaires, avis). N'invente rien. Donne : activité, produits ou services, public visé, positionnement, coordonnées publiques, points faibles visibles. Si tu ne trouves rien, réponds exactement : NON_TROUVE.",
            f"Site : {host} ({normalise_url(url)})",
        )
    except perplexity.PerplexityError as exc:
        raise SiteError(f"Site bloqué et recherche de secours indisponible : {str(exc)[:200]}") from exc
    if "NON_TROUVE" in text or not sources:
        raise SiteError("Le site bloque les lectures automatiques et la recherche web n'a rien trouvé de fiable à son sujet. Vous pouvez décrire votre activité dans la configuration.")
    emails = sorted(set(re.findall(r"[\w.\-+]+@[\w\-]+\.[\w.\-]+", text)))[:4]
    return {"url": normalise_url(url), "pages": [{"url": normalise_url(url), "title": host, "description": "", "headings": [], "text": text[:PAGE_TEXT * 2], "words": len(text.split())}], "emails": emails, "phones": [], "social": [], "schema": []}


def integrate(session: Session, company: Company) -> dict:
    """Crawl, understand, store, share, and turn the improvements into proposals."""

    from app.agents import service as agents

    if not company.website_url:
        raise SiteError("Aucun site web renseigné.")
    indirect = False
    try:
        site = crawl(company.website_url)
    except SiteError as exc:
        if not exc.blocked or not perplexity.configured():
            raise
        site = research(company.website_url)  # blocked for robots: read what the web knows about it
        indirect = True
        from app.browser import manager

        if manager.available():
            agents._ingest(session, company, {"category": "site web", "title": "Laisser l'IA lire votre site dans le navigateur", "summary": "Votre site bloque les lectures automatiques : un navigateur réel, suivi par vous, peut le lire en entier.", "why_it_matters": "L'analyse actuelle est indirecte et moins détaillée.", "suggested_action": {"type": "browser", "text": f"Ouvre {company.website_url}, parcours les pages principales (accueil, produits, à propos, contact) et résume l'activité, l'offre et les coordonnées.", "url": company.website_url}}, [], agent="analyste")
    analysis, by_model = understand(company.name, site)

    catalog = [n.lower() for (n,) in session.query(Product.name).filter(Product.company_id == company.id).limit(20000).all()]
    missing = [o for o in analysis["offer"] if not any(o.lower() in n or n in o.lower() for n in catalog)]

    context = BusinessContextService(session).get_or_create(company.id)
    config = dict(context.configuration or {})
    config["website"] = {
        "url": site["url"], "analysed_at": datetime.now(timezone.utc).isoformat(), "by_model": by_model, "pages": [{"url": p["url"], "title": p["title"], "words": p["words"]} for p in site["pages"]],
        "emails": site["emails"], "phones": site["phones"], "social": site["social"], "analysis": analysis, "not_in_catalog": missing[:12],
        "request": (config.get("website") or {}).get("request"), "indirect": indirect,
    }
    context.configuration = config
    session.commit()

    created = 0
    for imp in analysis["improvements"]:
        item = {"category": "site web", "title": f"Site web : {imp['title']}"[:240], "summary": imp.get("action") or imp["title"], "why_it_matters": imp["why"], "suggested_action": {"type": "task", "text": f"Site web : {imp['title']}"[:240]}}
        created += agents._ingest(session, company, item, [site["url"]], agent="analyste")
    for sync in analysis["syncs"]:
        item = {"category": "synchronisation", "title": f"Synchroniser : {sync['title']}"[:240], "summary": sync["title"], "why_it_matters": sync["why"], "suggested_action": {"type": "none"}}
        created += agents._ingest(session, company, item, [site["url"]], agent="analyste")
    if missing:
        item = {"category": "synchronisation", "title": f"{len(missing)} produit(s) ou service(s) du site absents de votre catalogue", "summary": ", ".join(missing[:8]), "why_it_matters": "Votre site présente une offre que le logiciel ne connaît pas : sans elle, marges et stocks ne sont pas suivis.", "suggested_action": {"type": "task", "text": "Compléter le catalogue avec l'offre du site"}}
        created += agents._ingest(session, company, item, [site["url"]], agent="analyste")
    session.commit()
    agents.remember(session, company.id, "analyste", "Analyse du site web", analysis["summary"], [i["title"] for i in analysis["improvements"]])
    return {"indirect": indirect, "pages": len(site["pages"]), "by_model": by_model, "created": created, "analysis": analysis, "not_in_catalog": missing[:12], "emails": site["emails"], "phones": site["phones"], "social": site["social"]}


def state(session: Session, company_id: uuid.UUID) -> dict | None:
    from app.configuration import service as config_service

    return config_service.get_configuration(session, company_id).get("website")


def request_creation(session: Session, company_id: uuid.UUID, notes: str | None) -> dict:
    context = BusinessContextService(session).get_or_create(company_id)
    config = dict(context.configuration or {})
    site = dict(config.get("website") or {})
    site["request"] = {"status": "requested", "at": datetime.now(timezone.utc).isoformat(), "notes": " ".join((notes or "").split())[:1000] or None}
    config["website"] = site
    context.configuration = config
    session.commit()
    return site["request"]
