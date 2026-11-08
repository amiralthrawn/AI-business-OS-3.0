"""Which proposal comes first.

A score per proposal: what the kind of card is worth, plus how close it is to
what the person said they care about when they configured the product
(goals, problems, external factors, tools), plus a boost for what unblocks
everything else while no sale or purchase is known yet.
"""

import re

from sqlalchemy.orm import Session

from app.configuration import service as config_service
from app.core.entities import AgentProposal, Company, Transaction

BASE = {"missing_info": 70, "initiative": 75, "navigateur": 60, "finding": 40}
UNBLOCKING = ("initiative", "suite", "navigateur", "question", "information")


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-zà-ÿ0-9]{5,}", text.lower())}


def rank(session: Session, company: Company, proposals: list[AgentProposal]) -> list[tuple[AgentProposal, int]]:
    config = config_service.get_configuration(session, company.id)
    liked = _words(" ".join([str(config.get("sector_custom") or ""), str(config.get("problems") or ""), str(config.get("external_factors") or ""),
                             *(" ".join(v) for v in (config.get("answers") or {}).values() if isinstance(v, list)),
                             *(str(v) for v in (config.get("answer_notes") or {}).values())]))
    no_data = session.query(Transaction).count() == 0
    out = []
    for p in proposals:
        key = "missing_info" if p.kind == "missing_info" else "navigateur" if p.action_type == "browser" else "initiative" if p.agent == "directeur" else "finding"
        score = BASE[key] + min(30, 10 * len(liked & _words(f"{p.title} {p.summary or ''} {p.why or ''}")))
        if no_data and (p.category in UNBLOCKING or key in ("missing_info", "navigateur")):
            score += 15
        if p.event_date is not None:
            score += 5
        out.append((p, score))
    out.sort(key=lambda t: (t[1], t[0].created_at), reverse=True)
    return out
