"""Step 19: Home as the Command Center -- a read/synthesis layer over the
Business State Snapshot, the Decision/Interpretation/Observation Event Log,
Risks/Opportunities and Tasks, never a parallel intelligence engine.

Covers the step's Definition-of-Done test list:
1. AI Priorities come from the Snapshot.
2. Risks are correctly exposed.
3. Opportunities are correctly exposed.
4. Decisions are correctly exposed.
5. PENDING_VALIDATION Tasks are exposed.
6. No action can be auto-executed from Home.
7. Recent Activity comes from the real Event Log.
8. Home never recomputes intelligence in parallel (identical to the Snapshot's own numbers).
9. Empty / insufficient context is handled explicitly.
10. Ask AI (the Orchestrator) still works alongside Home.
"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.ai.capabilities import build_capability_registry
from app.ai.llm import DeterministicLLMClient
from app.business_context.service import BusinessContextService
from app.core.entities import (
    Company,
    Customer,
    EventLogEntry,
    Product,
    Risk,
    RiskStatus,
    Supplier,
    Task,
    TaskStatus,
    Transaction,
    TransactionStatus,
    TransactionType,
)
from app.core.events.bus import InProcessEventBus
from app.core.events.log_handler import make_event_log_handler
from app.database import get_db
from app.decision.engine import run_decision_sweep
from app.dependencies import get_event_bus
from app.home.service import HomeService
from app.interpretation.engine import run_interpretation_sweep
from app.main import app
from app.observation import build_observable_registry
from app.observation.engine import run_observation_sweep
from app.snapshot.service import build_snapshot


def _bus(session_factory):
    bus = InProcessEventBus()
    bus.subscribe("*", make_event_log_handler(session_factory))
    return bus


def _seed_margin_risk_scenario(db_session):
    """The same real margin-deterioration chain used throughout steps 15-17:
    a declared 30% margin target, a supplier cost creep pushing the real
    margin well below it -> a real, material Business Event all the way
    through to a Decision."""

    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()
    BusinessContextService(db_session).update(company.id, declared_baselines={"margin_pct": 0.30})

    supplier = Supplier(company_id=company.id, name="Northline")
    db_session.add(supplier)
    db_session.flush()
    customer = Customer(company_id=company.id, name="Buyer Co")
    db_session.add(customer)
    db_session.flush()
    product = Product(company_id=company.id, supplier_id=supplier.id, name="Frame", sku="F-1")
    db_session.add(product)
    db_session.flush()

    now = datetime.now(timezone.utc)
    for i, cost in enumerate([400.0, 400.0, 900.0, 900.0]):
        db_session.add(
            Transaction(
                company_id=company.id, supplier_id=supplier.id, product_id=product.id,
                type=TransactionType.PURCHASE_ORDER, status=TransactionStatus.CONFIRMED,
                amount=cost, currency="EUR", occurred_at=now - timedelta(days=(4 - i) * 30),
            )
        )
    for i in range(4):
        db_session.add(
            Transaction(
                company_id=company.id, customer_id=customer.id, product_id=product.id,
                type=TransactionType.SALES_ORDER, status=TransactionStatus.CONFIRMED,
                amount=1000.0, currency="EUR", occurred_at=now - timedelta(days=(4 - i) * 30),
            )
        )
    db_session.commit()
    return company, supplier, product, customer


def _run_full_chain(db_session, bus, company_id):
    run_observation_sweep(db_session, bus, build_observable_registry(), company_id)
    run_interpretation_sweep(db_session, bus, build_capability_registry(), DeterministicLLMClient(), company_id)
    run_decision_sweep(db_session, bus, build_capability_registry(), DeterministicLLMClient(), company_id)


# --- 1 & 8. AI Priorities come from the Snapshot, with no parallel recomputation


def test_ai_priorities_match_the_snapshots_own_material_areas_exactly(db_session, session_factory):
    bus = _bus(session_factory)
    company, supplier, product, customer = _seed_margin_risk_scenario(db_session)
    _run_full_chain(db_session, bus, company.id)

    snapshot = build_snapshot(db_session, company.id)
    priorities = HomeService(db_session).get_ai_priorities(company.id)

    assert len(priorities) == len(snapshot.material_areas)
    for priority, area in zip(priorities, snapshot.material_areas):
        # Home never recomputes impact/urgency/confidence -- it re-hydrates
        # exactly what app.snapshot.service already produced.
        assert priority["kind"] == area.kind
        assert priority["title"] == area.title
        assert priority["impact"] == area.significance.impact
        assert priority["urgency"] == area.significance.urgency
        assert priority["confidence"] == area.significance.confidence
        assert priority["domain"] == area.domain

    decision_priority = next(p for p in priorities if p["kind"] == "decision")
    assert decision_priority["interpretation_type"] == "risk"
    assert decision_priority["recommendation"]
    assert decision_priority["explanation"]
    assert decision_priority["decision_options"]


def test_ai_priorities_link_back_to_an_existing_risk_detail_page(db_session, session_factory):
    bus = _bus(session_factory)
    company, supplier, product, customer = _seed_margin_risk_scenario(db_session)
    _run_full_chain(db_session, bus, company.id)

    from app.intelligence.risks.service import RiskDetectionService

    risk = RiskDetectionService(db_session, bus).evaluate_margin_trend(product.id)
    assert risk is not None

    priorities = HomeService(db_session).get_ai_priorities(company.id)

    risk_priority = next(p for p in priorities if p["kind"] == "risk")
    assert risk_priority["detail_kind"] == "risk"
    assert risk_priority["detail_id"] == risk.id


# --- 2 & 3. Risks / Opportunities are correctly exposed alongside priorities


def test_risks_and_opportunities_summaries_are_exposed_in_the_command_center(db_session, session_factory):
    bus = _bus(session_factory)
    company, supplier, product, customer = _seed_margin_risk_scenario(db_session)
    _run_full_chain(db_session, bus, company.id)

    from app.intelligence.risks.service import RiskDetectionService

    RiskDetectionService(db_session, bus).evaluate_margin_trend(product.id)

    view = HomeService(db_session).get_command_center(company.id)

    assert view["risks"]["total_risks"] == 1
    assert view["risks"]["recent_risks"][0].related_entity_id == product.id
    assert view["opportunities"]["total_opportunities"] == 0


# --- 4. Decisions are correctly exposed, re-hydrated not recomputed --------


def test_decisions_are_exposed_exactly_as_produced_by_decision_intelligence(db_session, session_factory):
    bus = _bus(session_factory)
    company, supplier, product, customer = _seed_margin_risk_scenario(db_session)
    _run_full_chain(db_session, bus, company.id)

    from app.decision.engine import DECISION_PROPOSED

    source_entry = db_session.query(EventLogEntry).filter_by(event_type=DECISION_PROPOSED).one()

    decisions = HomeService(db_session).get_decisions()

    assert len(decisions) == 1
    decision = decisions[0]
    assert decision["type"] == source_entry.payload["type"]
    assert decision["problem"] == source_entry.payload["problem"]
    assert decision["options"] == source_entry.payload["options"]
    assert decision["recommendation"] == source_entry.payload["recommendation"]
    assert decision["confidence"] == source_entry.payload["confidence"]


# --- 5 & 6. PENDING_VALIDATION Tasks are exposed; nothing auto-executes -----


def test_pending_tasks_are_exposed_and_home_never_executes_them(db_session, session_factory):
    bus = _bus(session_factory)
    # A brand-new, uncovered entity so the Decision sweep actually proposes
    # a Task (see app.decision.engine's dedup guard).
    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()
    BusinessContextService(db_session).update(company.id, declared_baselines={"margin_pct": 0.30})
    supplier = Supplier(company_id=company.id, name="Northline")
    db_session.add(supplier)
    db_session.flush()
    customer = Customer(company_id=company.id, name="Buyer Co")
    db_session.add(customer)
    db_session.flush()
    product = Product(company_id=company.id, supplier_id=supplier.id, name="Frame", sku="F-1")
    db_session.add(product)
    db_session.flush()
    now = datetime.now(timezone.utc)
    for i, cost in enumerate([400.0, 400.0, 900.0, 900.0]):
        db_session.add(
            Transaction(
                company_id=company.id, supplier_id=supplier.id, product_id=product.id,
                type=TransactionType.PURCHASE_ORDER, status=TransactionStatus.CONFIRMED,
                amount=cost, currency="EUR", occurred_at=now - timedelta(days=(4 - i) * 30),
            )
        )
    for i in range(4):
        db_session.add(
            Transaction(
                company_id=company.id, customer_id=customer.id, product_id=product.id,
                type=TransactionType.SALES_ORDER, status=TransactionStatus.CONFIRMED,
                amount=1000.0, currency="EUR", occurred_at=now - timedelta(days=(4 - i) * 30),
            )
        )
    db_session.commit()
    _run_full_chain(db_session, bus, company.id)

    task = db_session.query(Task).one()
    assert task.status == TaskStatus.PENDING_VALIDATION

    view = HomeService(db_session).get_command_center(company.id)
    assert view["tasks"]["pending_validation_tasks"] == 1
    assert view["tasks"]["recent_tasks"][0].id == task.id

    # Reading the Command Center repeatedly is a pure read: it has no
    # ActionExecutor, no approve/reject method, no way to change Task status.
    for _ in range(3):
        HomeService(db_session).get_command_center(company.id)
    db_session.refresh(task)
    assert task.status == TaskStatus.PENDING_VALIDATION
    assert not hasattr(HomeService, "approve_task")
    assert not hasattr(HomeService, "execute_task")


# --- 7. Recent Activity comes from the real Event Log -----------------------


def test_recent_activity_reflects_the_real_event_log(db_session, session_factory):
    bus = _bus(session_factory)
    company, supplier, product, customer = _seed_margin_risk_scenario(db_session)
    _run_full_chain(db_session, bus, company.id)

    view = HomeService(db_session).get_command_center(company.id)
    logged_event_types = {e.event_type for e in db_session.query(EventLogEntry).all()}
    home_event_types = {e.event_type for e in view["recent_events"]}

    assert home_event_types <= logged_event_types
    assert "DecisionProposed" in logged_event_types


# --- 9. Empty / insufficient context -----------------------------------------


def test_command_center_on_a_fresh_company_with_no_signals_is_explicitly_empty(db_session):
    company = Company(name="Fresh Co")
    db_session.add(company)
    db_session.commit()

    view = HomeService(db_session).get_command_center(company.id)

    assert view["priorities"] == []
    assert view["decisions"] == []
    assert view["risks"]["total_risks"] == 0
    assert view["opportunities"]["total_opportunities"] == 0
    assert view["tasks"]["pending_validation_tasks"] == 0


def test_command_center_with_no_company_at_all_is_explicitly_empty(db_session):
    view = HomeService(db_session).get_command_center(company_id=None)
    assert view["priorities"] == []


# --- 10. Ask AI still works, unaffected by Home's changes -------------------


def test_ask_ai_endpoint_still_works_via_the_orchestrator(db_session, session_factory):
    bus_dependency = session_factory

    def override_get_db():
        yield db_session

    def override_get_event_bus():
        return _bus(bus_dependency)

    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()
    customer = Customer(company_id=company.id, name="Metroline Corp")
    db_session.add(customer)
    db_session.commit()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_event_bus] = override_get_event_bus
    try:
        client = TestClient(app)
        home_response = client.get("/home")
        ask_response = client.post("/ai/ask", json={"question": "How is customer Metroline Corp doing?"})
    finally:
        app.dependency_overrides.clear()

    assert home_response.status_code == 200
    assert ask_response.status_code == 200
    body = ask_response.json()
    assert body["agent"] == "sales"
    assert "read_customer" in body["capabilities_used"]
