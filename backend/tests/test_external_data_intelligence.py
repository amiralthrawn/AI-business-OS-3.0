"""Step 22 -- External Data Intelligence: the full loop from a Mock
Provider's data all the way to a Human-in-the-Loop-approved external action,
reusing Observation/Interpretation/Decision/Actions unmodified in their
classification/reasoning logic. Covers the brief's three mandatory
demonstration cases (A: Supplier + Email, B: Website + Customer/Prospect,
C: Calendar + Business Context), cross-domain reasoning, and idempotence."""

from datetime import datetime, timedelta, timezone

from app.ai.capabilities import build_capability_registry
from app.ai.llm import DeterministicLLMClient
from app.ai.orchestrator import AIOrchestrator
from app.business_context.service import BusinessContextService
from app.connectors.calendar.mock import MockCalendarProvider
from app.connectors.email.mock import MockEmailProvider
from app.connectors.ingestion import ingest_calendar, ingest_email, ingest_website
from app.connectors.website.mock import MockWebsiteProvider
from app.core.entities import (
    Communication,
    CommunicationDirection,
    Company,
    Contact,
    Customer,
    EventLogEntry,
    RelatedEntityType,
    Supplier,
    Task,
    TaskStatus,
)
from app.core.entity_context import get_entity_context
from app.core.events.bus import InProcessEventBus
from app.core.events.log_handler import make_event_log_handler
from app.decision.engine import run_decision_sweep
from app.home.service import HomeService
from app.interpretation.engine import EVENT_INTERPRETED, run_interpretation_sweep
from app.observation import build_observable_registry
from app.observation.engine import run_observation_sweep


def _bus(session_factory):
    bus = InProcessEventBus()
    bus.subscribe("*", make_event_log_handler(session_factory))
    return bus


def _seed_company_with_supplier_and_customer(db_session):
    """A minimal, isolated company -- no pre-existing Risk/Opportunity from
    the older per-metric rules, so the full loop reaches Action Proposal
    without being shadowed (unlike the main seed's own entities, see
    brain/external_data_intelligence.md)."""

    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()
    BusinessContextService(db_session).update(company.id, declared_baselines={"unanswered_message_age_days": 3})
    supplier = Supplier(company_id=company.id, name="Northline Steel")
    db_session.add(supplier)
    db_session.flush()
    customer = Customer(company_id=company.id, name="Metroline Corp")
    db_session.add(customer)
    db_session.flush()
    db_session.commit()
    return company, supplier, customer


def _run_full_chain(db_session, bus, company_id):
    registry = build_capability_registry()
    llm = DeterministicLLMClient()
    observation_result = run_observation_sweep(db_session, bus, build_observable_registry(), company_id)
    interpretation_result = run_interpretation_sweep(db_session, bus, registry, llm, company_id)
    decision_result = run_decision_sweep(db_session, bus, registry, llm, company_id)
    return observation_result, interpretation_result, decision_result


# --- Cas A: Supplier + Email --------------------------------------------------


def test_cas_a_supplier_email_flows_through_observation_interpretation_and_decision(db_session, session_factory):
    bus = _bus(session_factory)
    company, supplier, customer = _seed_company_with_supplier_and_customer(db_session)

    email_result = ingest_email(db_session, MockEmailProvider(), company.id)
    assert email_result.created > 0

    observation_result, interpretation_result, decision_result = _run_full_chain(db_session, bus, company.id)

    # Northline Steel's real, old, unanswered renegotiation email produced a
    # material Observation -> Business Event -> Interpretation -> Decision.
    assert observation_result["business_events_published"] >= 1
    assert interpretation_result["by_type"]["risk"] >= 1
    assert decision_result["by_type"]["risk"] >= 1

    interp_entry = (
        db_session.query(EventLogEntry)
        .filter_by(event_type=EVENT_INTERPRETED)
        .filter(EventLogEntry.payload.like('%"entity_name": "Northline Steel"%'))
        .one()
    )
    assert "Steel pricing renegotiation" in str(interp_entry.payload["explanation"])
    assert interp_entry.payload["type"] == "risk"

    # Traceable: the Communication and the Interpretation share the same
    # underlying message.
    comm = db_session.query(Communication).filter_by(external_id="email_001").one()
    assert comm.related_entity_type == RelatedEntityType.SUPPLIER
    assert comm.related_entity_id == supplier.id


# --- Cas B: Website + Customer/Prospect --------------------------------------


def test_cas_b_website_inquiry_from_a_known_customer_resolves_and_can_be_observed(db_session, session_factory):
    bus = _bus(session_factory)
    company, supplier, customer = _seed_company_with_supplier_and_customer(db_session)

    website_result = ingest_website(db_session, MockWebsiteProvider(), company.id)
    assert website_result.created > 0

    # web_004's sender domain matches "Metroline Corp".
    comm = db_session.query(Communication).filter_by(external_id="web_004").one()
    assert comm.related_entity_type == RelatedEntityType.CUSTOMER
    assert comm.related_entity_id == customer.id

    context = get_entity_context(db_session, RelatedEntityType.CUSTOMER, customer.id)
    assert any(c["channel"] == "website" for c in context["communications"])

    _run_full_chain(db_session, bus, company.id)
    interp_entries = (
        db_session.query(EventLogEntry)
        .filter_by(event_type=EVENT_INTERPRETED)
        .filter(EventLogEntry.payload.like('%"entity_name": "Metroline Corp"%'))
        .all()
    )
    assert len(interp_entries) >= 1


def test_cas_b_website_inquiry_from_an_unknown_prospect_never_creates_a_customer(db_session, session_factory):
    bus = _bus(session_factory)
    company, supplier, customer = _seed_company_with_supplier_and_customer(db_session)

    ingest_website(db_session, MockWebsiteProvider(), company.id)

    # web_001 (Dana Whitfield / Brookfield Industrial) is a genuine unknown
    # prospect -- no Customer/Supplier exists or is ever created for them.
    comm = db_session.query(Communication).filter_by(external_id="web_001").one()
    assert comm.related_entity_type is None
    assert comm.related_entity_id is None

    contact = db_session.query(Contact).filter_by(email="dana.whitfield@brookfieldindustrial.example").one()
    assert contact.related_entity_type is None
    assert db_session.query(Customer).filter_by(name="Brookfield Industrial").count() == 0

    # An unresolved contact produces no per-entity Observation (there is no
    # Supplier/Customer row to attach Significance to) -- correct absence,
    # not a bug: the Observation Engine iterates real entity rows only.
    _run_full_chain(db_session, bus, company.id)
    assert (
        db_session.query(EventLogEntry)
        .filter_by(event_type=EVENT_INTERPRETED)
        .filter(EventLogEntry.payload.like("%Brookfield%"))
        .count()
        == 0
    )


# --- Cas C: Calendar + Business Context --------------------------------------


def test_cas_c_calendar_event_is_traceable_to_its_business_entity(db_session, session_factory):
    bus = _bus(session_factory)
    company, supplier, customer = _seed_company_with_supplier_and_customer(db_session)

    calendar_result = ingest_calendar(db_session, MockCalendarProvider(), company.id)
    assert calendar_result.created > 0

    # calendar_003 ("Northline Steel pricing call") resolves to the real Supplier.
    comm = db_session.query(Communication).filter_by(external_id="calendar_003").one()
    assert comm.related_entity_type == RelatedEntityType.SUPPLIER
    assert comm.related_entity_id == supplier.id

    context = get_entity_context(db_session, RelatedEntityType.SUPPLIER, supplier.id)
    assert any(c["channel"] == "calendar" for c in context["communications"])


# --- Cross-domain reasoning ---------------------------------------------------


def test_cross_domain_question_about_the_supplier_pulls_in_multiple_domains(db_session, session_factory):
    bus = _bus(session_factory)
    company, supplier, customer = _seed_company_with_supplier_and_customer(db_session)
    ingest_email(db_session, MockEmailProvider(), company.id)

    orchestrator = AIOrchestrator(db_session, build_capability_registry(), DeterministicLLMClient(), bus)
    result = orchestrator.ask("Why is Northline Steel important for our margin?")

    assert "finance" in result.agent
    assert "procurement" in result.agent
    assert "read_supplier" in result.capabilities_used


# --- Decision -> Action Proposal -> Human Validation -> Connector -----------


def test_full_loop_proposes_a_meeting_and_executes_it_on_approval(db_session, session_factory):
    """The brief's own example: Supplier communication -> Decision -> Propose
    meeting -> Human validation -> Mock Calendar. Procurement-domain
    external decisions propose a follow-up MEETING."""

    bus = _bus(session_factory)
    company, supplier, customer = _seed_company_with_supplier_and_customer(db_session)
    ingest_email(db_session, MockEmailProvider(), company.id)

    _, _, decision_result = _run_full_chain(db_session, bus, company.id)
    assert decision_result["actions_proposed"] >= 1

    task = db_session.query(Task).filter_by(pending_action="connector_followup_meeting").one()
    assert task.status == TaskStatus.PENDING_VALIDATION  # never auto-executed
    assert task.related_entity_id == supplier.id

    from app.actions.executor import ActionExecutor
    from app.actions.service import ActionsService

    calendar_provider = MockCalendarProvider()
    before = len(calendar_provider.list_events(datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(days=30)))

    # Patch the shared connector registry's calendar provider so this test
    # observes the exact instance the executor calls through.
    from app.connectors.registry import connector_registry

    connector_registry.register("calendar", calendar_provider)
    try:
        executor = ActionExecutor(ActionsService(db_session, bus))
        approved = executor.approve(task.id)
    finally:
        connector_registry.register("calendar", MockCalendarProvider())

    assert approved.status == TaskStatus.EXECUTED
    after = calendar_provider.list_events(datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(days=30))
    assert len(after) == before + 1
    assert after[-1].attendees == ["procurement@northlinesteel.com"]


def test_full_loop_proposes_a_reply_and_executes_it_on_approval(db_session, session_factory):
    """Customer inquiry -> Decision -> Propose response -> Human validation
    -> Mock Email. Sales-domain external decisions propose a follow-up
    EMAIL reply."""

    bus = _bus(session_factory)
    company, supplier, customer = _seed_company_with_supplier_and_customer(db_session)

    now = datetime.now(timezone.utc)
    db_session.add(
        Communication(
            company_id=company.id, channel="email", direction=CommunicationDirection.INBOUND,
            subject="Can we increase our order?", body="We'd like to expand our order volume.",
            occurred_at=now - timedelta(days=9),
            related_entity_type=RelatedEntityType.CUSTOMER, related_entity_id=customer.id,
        )
    )
    db_session.add(Contact(company_id=company.id, name="Alex", email="alex@metrolinecorp.example",
                            related_entity_type=RelatedEntityType.CUSTOMER, related_entity_id=customer.id))
    db_session.commit()

    _, _, decision_result = _run_full_chain(db_session, bus, company.id)
    assert decision_result["actions_proposed"] >= 1

    task = db_session.query(Task).filter_by(pending_action="connector_followup_email").one()
    assert task.status == TaskStatus.PENDING_VALIDATION

    from app.actions.executor import ActionExecutor
    from app.actions.service import ActionsService
    from app.connectors.registry import connector_registry

    email_provider = MockEmailProvider()
    before = len(email_provider.list_messages())
    connector_registry.register("email", email_provider)
    try:
        executor = ActionExecutor(ActionsService(db_session, bus))
        approved = executor.approve(task.id)
    finally:
        connector_registry.register("email", MockEmailProvider())

    assert approved.status == TaskStatus.EXECUTED
    after = email_provider.list_messages()
    assert len(after) == before + 1
    assert after[-1].recipients == ["alex@metrolinecorp.example"]
    assert after[-1].direction == "outbound"


# --- Idempotence across sync + sweep -----------------------------------------


def test_two_syncs_then_two_sweeps_never_duplicate_anything(db_session, session_factory):
    bus = _bus(session_factory)
    company, supplier, customer = _seed_company_with_supplier_and_customer(db_session)

    first_sync = ingest_email(db_session, MockEmailProvider(), company.id)
    second_sync = ingest_email(db_session, MockEmailProvider(), company.id)
    assert second_sync.created == 0
    assert second_sync.skipped == first_sync.created

    first_sweep = _run_full_chain(db_session, bus, company.id)
    second_sweep = _run_full_chain(db_session, bus, company.id)

    assert second_sweep[0]["business_events_published"] == 0
    assert second_sweep[1]["observations_interpreted"] == 0
    assert second_sweep[2]["decisions_made"] == 0
    assert second_sweep[2]["actions_proposed"] == 0

    # No duplicate Tasks from the second, fully-idempotent sweep.
    assert db_session.query(Task).filter_by(pending_action="connector_followup_meeting").count() == 1


# --- Existing pipelines still function -----------------------------------


def test_home_naturally_surfaces_the_new_external_signal_without_modification(db_session, session_factory):
    bus = _bus(session_factory)
    company, supplier, customer = _seed_company_with_supplier_and_customer(db_session)
    ingest_email(db_session, MockEmailProvider(), company.id)
    _run_full_chain(db_session, bus, company.id)

    view = HomeService(db_session).get_command_center(company.id)
    assert any(p["kind"] == "decision" for p in view["priorities"])
    assert len(view["decisions"]) >= 1
    assert view["tasks"]["pending_validation_tasks"] >= 1
