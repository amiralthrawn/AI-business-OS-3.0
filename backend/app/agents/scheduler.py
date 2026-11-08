"""Keeps the agents working around the clock, at a pace that changes with the
hour (service.cadence_hours): the Veilleur searches the web, the Analyste
re-reads the numbers. One loop per backend process; each company is handled
in its own scoped session so nothing crosses companies."""

import asyncio
import logging

from app.agents import directeur, perplexity, service
from app.core.entities import Company
from app.core.tenant_scope import scope_session
from app.database import SessionLocal

log = logging.getLogger("agents")
TICK_SECONDS = 300


def _sync_mailboxes(db, company) -> None:
    """Connected mailboxes are re-read about every hour."""

    from datetime import datetime, timedelta, timezone

    from app.connectors import oauth
    from app.connectors.oauth_router import sync

    for entry in oauth.status(db, company.id):
        if not entry["connected"]:
            continue
        last = entry["last_sync"]
        if last and datetime.now(timezone.utc) - datetime.fromisoformat(last) < timedelta(hours=1):
            continue
        try:
            sync(db, company, entry["provider"])
        except oauth.OAuthError:
            db.rollback()


def run_cycle() -> None:
    with SessionLocal() as listing:
        companies = [(c.id) for c in listing.query(Company).all()]
    for company_id in companies:
        with SessionLocal() as db:
            scope_session(db, company_id)
            company = db.query(Company).first()
            if company is None or not service.get_settings(db, company.id)["enabled"]:
                continue
            try:
                _sync_mailboxes(db, company)
                hours = service.cadence_hours()
                if service.is_due(db, company.id, "analyste", 1):
                    service.run_analyste(db, company)
                if perplexity.configured() and service.is_due(db, company.id, "veilleur", hours):
                    service.run_veilleur(db, company)
                if service.is_due(db, company.id, "directeur", 1):
                    directeur.run_directeur(db, company)
            except Exception:  # one company's failure must never stop the others
                db.rollback()
                log.exception("agent cycle failed for %s", company_id)


async def loop() -> None:
    while True:
        try:
            await asyncio.to_thread(run_cycle)
        except Exception:
            log.exception("agent loop error")
        await asyncio.sleep(TICK_SECONDS)
