"""Step 21/22: proof that re-running connector ingestion and every
Intelligence sweep against an already-seeded database is a pure no-op --
idempotence holds across the whole chain, not just within one layer.
Connectors themselves still contain no business intelligence (they only
ever write Communication/Document/Contact rows); since step 22, two
Observables DO read those Communications (see
brain/external_data_intelligence.md), which is exactly what this test's
zero-new-events assertions confirm still behaves correctly on a second run."""

from app.ai.capabilities import build_capability_registry
from app.ai.llm import DeterministicLLMClient
from app.ai.orchestrator import AIOrchestrator
from app.connectors.calendar.mock import MockCalendarProvider
from app.connectors.email.mock import MockEmailProvider
from app.connectors.ingestion import ingest_calendar, ingest_email, ingest_website
from app.connectors.website.mock import MockWebsiteProvider
from app.core.entities import Communication, Company, Contact, Risk
from app.decision.engine import run_decision_sweep
from app.event_bus import build_event_bus
from app.home.service import HomeService
from app.interpretation.engine import run_interpretation_sweep
from app.observation import build_observable_registry
from app.observation.engine import run_observation_sweep
from data.seed import seed


def test_connector_ingestion_alongside_the_full_seed_does_not_change_pipeline_results(db_session, session_factory):
    bus = build_event_bus(session_factory)

    # seed() itself ingests all three Mock Providers (step 21) alongside the
    # rest of the demo dataset -- confirm that data is really there first.
    seed(db_session, bus)
    company = db_session.query(Company).one()

    assert db_session.query(Communication).filter(Communication.source.isnot(None)).count() > 0
    assert db_session.query(Contact).count() > 0

    # Re-running ingestion (as a human triggering POST /connectors/{type}/sync
    # again would) must be a pure no-op against data seed() already ingested.
    email_result = ingest_email(db_session, MockEmailProvider(), company.id)
    calendar_result = ingest_calendar(db_session, MockCalendarProvider(), company.id)
    website_result = ingest_website(db_session, MockWebsiteProvider(), company.id)

    assert email_result.created == 0
    assert calendar_result.created == 0
    assert website_result.created == 0

    # Re-run every intelligence layer's sweep -- results must be identical
    # to what a fresh seed alone already produces (steps 15-17's own
    # numbers), since connectors write only Communication/Document/Contact,
    # none of which any Observable reads.
    registry = build_capability_registry()
    llm = DeterministicLLMClient()

    observation_result = run_observation_sweep(db_session, bus, build_observable_registry(), company.id)
    assert observation_result["business_events_published"] == 0  # already published by seed()

    interpretation_result = run_interpretation_sweep(db_session, bus, registry, llm, company.id)
    assert interpretation_result["observations_interpreted"] == 0  # already interpreted by seed()

    decision_result = run_decision_sweep(db_session, bus, registry, llm, company.id)
    assert decision_result["decisions_made"] == 0  # already decided by seed()

    # AI Orchestrator cross-domain question still works, unaffected.
    orchestrator = AIOrchestrator(db_session, registry, llm, bus)
    result = orchestrator.ask("Why is our margin declining?")
    assert "finance" in result.agent

    # Home still reflects the same priorities/decisions the seed produced --
    # identical to a fresh seed's own numbers, unaffected by a repeated sync.
    view = HomeService(db_session).get_command_center(company.id)
    assert len(view["priorities"]) == 7
    assert len(view["decisions"]) == 7
    assert view["risks"]["total_risks"] == db_session.query(Risk).count()

    # Ingestion writes Data Core rows directly; it never publishes a
    # Business Event, so connector-sourced Communications are invisible to
    # Home's Recent Activity (Event Log-derived) -- a real, documented
    # boundary (see brain/connectors.md), not an oversight.
    recent_event_sources = {e.source for e in view["recent_events"]}
    assert "mock_email" not in recent_event_sources
    assert "mock_calendar" not in recent_event_sources
    assert "mock_website" not in recent_event_sources
