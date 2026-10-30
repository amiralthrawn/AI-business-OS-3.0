"""Proof that the Business State Snapshot is fed by the Decision
Intelligence Engine's Business Events -- a "decision" area (options,
trade-offs, recommendation) supersedes the "interpretation" area for the
same entity, and both still defer to an existing open Risk/Opportunity from
the older per-metric rules, exactly like app.interpretation's own Snapshot
integration (see tests/test_interpretation_snapshot_integration.py and
brain/decision_intelligence.md)."""

from datetime import datetime, timedelta, timezone

from app.ai.capabilities import build_capability_registry
from app.ai.llm import DeterministicLLMClient
from app.business_context.service import BusinessContextService
from app.core.entities import Company, Customer, Product, Risk, Supplier, Transaction, TransactionStatus, TransactionType
from app.core.events.bus import InProcessEventBus
from app.core.events.log_handler import make_event_log_handler
from app.decision.engine import run_decision_sweep
from app.interpretation.engine import run_interpretation_sweep
from app.observation import build_observable_registry
from app.observation.engine import run_observation_sweep
from app.snapshot.service import build_snapshot


def _bus(session_factory):
    bus = InProcessEventBus()
    bus.subscribe("*", make_event_log_handler(session_factory))
    return bus


def _seed_margin_risk_scenario(db_session):
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


def test_snapshot_shows_a_decision_area_with_options_for_an_uncovered_entity(db_session, session_factory):
    bus = _bus(session_factory)
    company, supplier, product, customer = _seed_margin_risk_scenario(db_session)
    _run_full_chain(db_session, bus, company.id)

    snapshot = build_snapshot(db_session, company.id)

    decision_areas = [a for a in snapshot.areas if a.kind == "decision"]
    assert len(decision_areas) == 1
    area = decision_areas[0]
    assert area.interpretation_type == "risk"
    assert area.recommendation  # the chosen option
    assert area.explanation  # the recommendation's reasoning
    assert area.decision_options and len(area.decision_options) >= 2
    assert area.entity_id == product.id
    assert area in snapshot.material_areas

    # Superseded, not duplicated: no "interpretation" or "observation" area
    # remains for the same event once a Decision exists for it.
    assert not any(a.kind in ("interpretation", "observation") for a in snapshot.areas)


def test_snapshot_still_prefers_an_existing_open_risk_over_the_decision(db_session, session_factory):
    bus = _bus(session_factory)
    company, supplier, product, customer = _seed_margin_risk_scenario(db_session)
    _run_full_chain(db_session, bus, company.id)

    from app.intelligence.risks.service import RiskDetectionService

    RiskDetectionService(db_session, bus).evaluate_margin_trend(product.id)
    assert db_session.query(Risk).count() == 1

    snapshot = build_snapshot(db_session, company.id)

    areas_for_product = [a for a in snapshot.areas if a.entity_id == product.id]
    assert len(areas_for_product) == 1
    assert areas_for_product[0].kind == "risk"
