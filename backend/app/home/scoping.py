"""What each person sees on Home (V3 step 3).

`GET /home` used to return the whole company's picture to anyone signed in;
only the front end hid parts of it. Here the response is cut on the server to
what the profile may view (its role plus the director's grants and revokes),
and a short briefing, written from that same cut, opens the page.
"""

from app.access import policy as access
from app.access.deps import CurrentUser
from app.configuration.service import ai_profile, get_configuration
from app.core.i18n import tx

# Which permission opens a business domain. A domain not listed here is an
# intelligence topic: whoever can view intelligence sees it.
_DOMAIN_PERMISSION = {
    "finance": access.VIEW_FINANCE,
    "accounting": access.VIEW_FINANCE,
    "procurement": access.VIEW_PROCUREMENT,
    "sales": access.VIEW_SALES,
    "people": access.VIEW_PEOPLE,
    "hr": access.VIEW_PEOPLE,
    "communications": access.VIEW_COMMUNICATIONS,
}

# What the person can look into, in the order they are listed to them.
_VISIBLE_AREAS = (
    (access.VIEW_FINANCE, ("Finance", "Finance")),
    (access.VIEW_SALES, ("Ventes", "Sales")),
    (access.VIEW_PROCUREMENT, ("Achats", "Procurement")),
    (access.VIEW_COMMUNICATIONS, ("Communications", "Communications")),
    (access.VIEW_PEOPLE, ("Équipe", "People")),
    (access.VIEW_TREASURY, ("Trésorerie", "Treasury")),
)


def domain_visible(user: CurrentUser, domain: str | None) -> bool:
    return user.can(access.VIEW_INTELLIGENCE) and user.can(_DOMAIN_PERMISSION.get(domain or "", access.VIEW_INTELLIGENCE))


def task_visible(user: CurrentUser, domain: str | None) -> bool:
    """A task is visible to whoever may approve it or may view its domain."""

    if domain is None or user.can_approve(domain):
        return True
    return user.can(_DOMAIN_PERMISSION.get(domain, access.VIEW_INTELLIGENCE))


def scope_home(data: dict, user: CurrentUser) -> dict:
    scoped = dict(data)

    sees_intelligence = user.can(access.VIEW_INTELLIGENCE)
    scoped["priorities"] = [p for p in data["priorities"] if domain_visible(user, p["domain"])]
    scoped["decisions"] = [d for d in data["decisions"] if domain_visible(user, d["domain"])]
    if not sees_intelligence:
        scoped["risks"] = {"total_risks": 0, "high_risks": 0, "recent_risks": []}
        scoped["opportunities"] = {"total_opportunities": 0, "recent_opportunities": []}
        scoped["recent_events"] = []
    if not user.can(access.VIEW_ACTIONS):
        scoped["tasks"] = {"total_tasks": 0, "pending_validation_tasks": 0, "recent_tasks": []}
    if sees_intelligence or user.can(access.VIEW_ACTIONS):
        scoped["os_activity"] = [a for a in data["os_activity"] if a["domain"] is None or domain_visible(user, a["domain"])]
    else:
        scoped["os_activity"] = []
    if not user.can(access.VIEW_COMMUNICATIONS):
        scoped["company_narrative"] = []

    overview = dict(data["overview"])
    for field, permission in (
        ("customer_count", access.VIEW_SALES),
        ("supplier_count", access.VIEW_PROCUREMENT),
        ("product_count", access.VIEW_CATALOG),
        ("transaction_count", access.VIEW_FINANCE),
    ):
        if not user.can(permission):
            overview[field] = 0
    scoped["overview"] = overview
    return scoped


def viewer_and_briefing(session, company_id, scoped: dict, user: CurrentUser) -> dict:
    profile = user.profile
    areas = [tx(*labels) for permission, labels in _VISIBLE_AREAS if user.can(permission)]
    role = (profile.custom_role.name if profile is not None and profile.custom_role is not None else access.role_label(user.role))
    viewer = {
        "name": profile.name if profile is not None else None,
        "role": role,
        "job_title": profile.job_title if profile is not None else None,
        "areas": areas,
    }

    to_decide = [p for p in scoped["priorities"] if p["kind"] in ("risk", "opportunity", "decision", "interpretation")]
    pending = scoped["tasks"]["pending_validation_tasks"]
    lines: list[str] = []
    if to_decide:
        top = to_decide[0]
        lines.append(tx(f"Priorité : {top['title']}", f"Top priority: {top['title']}"))
    if pending:
        lines.append(
            tx(f"{pending} {'action attend' if pending == 1 else 'actions attendent'} votre validation.", f"{pending} {'action is' if pending == 1 else 'actions are'} waiting for your approval.")
        )
    if to_decide:
        headline = tx(
            f"{len(to_decide)} {'sujet mérite' if len(to_decide) == 1 else 'sujets méritent'} votre attention aujourd'hui.",
            f"{len(to_decide)} {'topic deserves' if len(to_decide) == 1 else 'topics deserve'} your attention today.",
        )
    elif pending:
        headline = tx("Des actions attendent votre validation.", "Some actions are waiting for your approval.")
    else:
        headline = tx("Rien d'urgent pour le moment.", "Nothing urgent right now.")

    profile_ai = ai_profile(get_configuration(session, company_id)) if company_id is not None else None
    if profile_ai and profile_ai.get("sector_label"):
        metrics = ", ".join(profile_ai["key_metrics"][:3])
        lines.append(tx(f"Pour votre activité ({profile_ai['sector_label']}), je suis surtout : {metrics}.", f"For your business ({profile_ai['sector_label']}), I mainly follow: {metrics}."))
    if not scoped["priorities"] and company_id is not None and not scoped["overview"]["customer_count"] and not scoped["overview"]["supplier_count"]:
        lines.append(tx("Importez vos données (Configuration → Données de vos outils) : l'IA pourra alors vous faire de vraies recommandations.", "Import your data (Settings → Data from your tools): the AI can then make real recommendations."))

    return {"viewer": viewer, "briefing": {"headline": headline, "lines": lines}}


def scope_tasks(session, user: CurrentUser) -> dict:
    """Pending approvals are the ones this person can actually approve; other
    recent tasks only when their domain is one the person may see."""

    from app.core.entities import Task
    from app.core.entities.task import TaskStatus

    if not user.can(access.VIEW_ACTIONS):
        return {"total_tasks": 0, "pending_validation_tasks": 0, "recent_tasks": []}
    pending = session.query(Task).filter_by(status=TaskStatus.PENDING_VALIDATION).order_by(Task.created_at.desc()).all()
    mine = [t for t in pending if user.can_approve(t.domain)]
    recent = session.query(Task).order_by(Task.created_at.desc()).limit(10).all()
    others = [t for t in recent if t.status != TaskStatus.PENDING_VALIDATION and (t.domain is None or domain_visible(user, t.domain))]
    visible_total = len(mine) + len([t for t in session.query(Task).filter(Task.status != TaskStatus.PENDING_VALIDATION).all() if t.domain is None or domain_visible(user, t.domain)])
    return {"total_tasks": visible_total, "pending_validation_tasks": len(mine), "recent_tasks": [*mine[:10], *others[:5]]}
