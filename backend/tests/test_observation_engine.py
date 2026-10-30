from datetime import datetime, timedelta, timezone

from app.business_context.service import BusinessContextService
from app.core.entities import (
    Company,
    Customer,
    EventLogEntry,
    Product,
    RelatedEntityType,
    Supplier,
    Transaction,
    TransactionStatus,
    TransactionType,
)
from app.observation import build_observable_registry
from app.observation.engine import OBSERVATION_DETECTED, compute_observation, run_observation_sweep


def _company_with_context(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()
    context = BusinessContextService(db_session).get_or_create(company.id)
    return company, context


def _margin_setup(db_session, company, cost_series, revenue_amount=1000.0):
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
    for i, cost in enumerate(cost_series):
        db_session.add(
            Transaction(
                company_id=company.id, supplier_id=supplier.id, product_id=product.id,
                type=TransactionType.PURCHASE_ORDER, status=TransactionStatus.CONFIRMED,
                amount=cost, currency="EUR", occurred_at=now - timedelta(days=(len(cost_series) - i) * 30),
            )
        )
    for i in range(len(cost_series)):
        db_session.add(
            Transaction(
                company_id=company.id, customer_id=customer.id, product_id=product.id,
                type=TransactionType.SALES_ORDER, status=TransactionStatus.CONFIRMED,
                amount=revenue_amount, currency="EUR", occurred_at=now - timedelta(days=(len(cost_series) - i) * 30),
            )
        )
    db_session.commit()
    return supplier, product, customer


# --- Observation computation --------------------------------------------------


def test_compute_observation_flags_a_real_anomaly(db_session):
    company, context = _company_with_context(db_session)
    supplier, product, customer = _margin_setup(db_session, company, [400.0, 400.0, 600.0, 600.0])

    registry = build_observable_registry()
    observation = compute_observation(db_session, registry.get("margin_pct"), product.id, context)

    assert observation.is_anomalous is True
    assert observation.significance.impact in {"medium", "high"}
    assert observation.baseline_source == "observed_history"


def test_compute_observation_is_normal_for_stable_behavior(db_session):
    company, context = _company_with_context(db_session)
    # Flat cost, flat revenue -> no margin deterioration.
    supplier, product, customer = _margin_setup(db_session, company, [500.0, 500.0, 500.0, 500.0])

    registry = build_observable_registry()
    observation = compute_observation(db_session, registry.get("margin_pct"), product.id, context)

    assert observation.is_anomalous is False


# --- Sweep: discovery, publication, idempotence -------------------------------


def test_sweep_publishes_a_business_event_for_a_real_anomaly(db_session, session_factory):
    from app.core.events.bus import InProcessEventBus
    from app.core.events.log_handler import make_event_log_handler

    company, _ = _company_with_context(db_session)
    _margin_setup(db_session, company, [400.0, 400.0, 600.0, 600.0])

    bus = InProcessEventBus()
    bus.subscribe("*", make_event_log_handler(session_factory))
    registry = build_observable_registry()

    result = run_observation_sweep(db_session, bus, registry, company.id)

    assert result["anomalies_detected"] >= 1
    assert result["business_events_published"] >= 1

    entries = db_session.query(EventLogEntry).filter_by(event_type=OBSERVATION_DETECTED).all()
    assert len(entries) == result["business_events_published"]
    assert entries[0].source == "observation_engine"
    assert entries[0].payload["observable"] == "margin_pct"


def test_sweep_produces_no_event_for_normal_behavior(db_session, event_bus):
    company, _ = _company_with_context(db_session)
    _margin_setup(db_session, company, [500.0, 500.0, 500.0, 500.0])

    registry = build_observable_registry()
    result = run_observation_sweep(db_session, event_bus, registry, company.id)

    assert result["anomalies_detected"] == 0
    assert result["business_events_published"] == 0


def test_sweep_run_twice_does_not_duplicate_events(db_session, session_factory):
    from app.core.events.bus import InProcessEventBus
    from app.core.events.log_handler import make_event_log_handler

    company, _ = _company_with_context(db_session)
    _margin_setup(db_session, company, [400.0, 400.0, 600.0, 600.0])

    bus = InProcessEventBus()
    bus.subscribe("*", make_event_log_handler(session_factory))
    registry = build_observable_registry()

    first = run_observation_sweep(db_session, bus, registry, company.id)
    second = run_observation_sweep(db_session, bus, registry, company.id)

    assert first["business_events_published"] >= 1
    assert second["business_events_published"] == 0

    entries = db_session.query(EventLogEntry).filter_by(event_type=OBSERVATION_DETECTED).all()
    assert len(entries) == first["business_events_published"]


def test_sweep_accumulates_observations_across_multiple_observables(db_session, event_bus):
    company, _ = _company_with_context(db_session)
    _margin_setup(db_session, company, [400.0, 400.0, 600.0, 600.0])

    supplier2 = Supplier(company_id=company.id, name="Iberia")
    db_session.add(supplier2)
    db_session.flush()
    product2 = Product(company_id=company.id, supplier_id=supplier2.id, name="Hose", sku="H-1")
    db_session.add(product2)
    db_session.flush()
    now = datetime.now(timezone.utc)
    for i, delay in enumerate([1.0, 1.0, 5.0, 5.0]):
        occurred_at = now - timedelta(days=(4 - i) * 30)
        db_session.add(
            Transaction(
                company_id=company.id, supplier_id=supplier2.id, product_id=product2.id,
                type=TransactionType.PURCHASE_ORDER, status=TransactionStatus.CONFIRMED,
                amount=100.0, currency="EUR", occurred_at=occurred_at,
                expected_at=occurred_at - timedelta(days=delay),
            )
        )
    db_session.commit()

    registry = build_observable_registry()
    result = run_observation_sweep(db_session, event_bus, registry, company.id)

    # Two independent anomalies (margin on one product, delivery on an
    # unrelated supplier) -- both observed, both surfaced.
    assert result["anomalies_detected"] == 2
    assert result["business_events_published"] == 2


# --- Cross-domain correlation --------------------------------------------------


def test_sweep_correlates_a_products_margin_issue_with_its_own_supplier(db_session, session_factory):
    from app.core.events.bus import InProcessEventBus
    from app.core.events.log_handler import make_event_log_handler

    company, _ = _company_with_context(db_session)
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
    # Margin deterioration on the product...
    for i, cost in enumerate([400.0, 400.0, 600.0, 600.0]):
        occurred_at = now - timedelta(days=(4 - i) * 30)
        db_session.add(
            Transaction(
                company_id=company.id, supplier_id=supplier.id, product_id=product.id,
                type=TransactionType.PURCHASE_ORDER, status=TransactionStatus.CONFIRMED,
                amount=cost, currency="EUR", occurred_at=occurred_at,
                expected_at=occurred_at - timedelta(days=[1.0, 1.0, 5.0, 5.0][i]),
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

    bus = InProcessEventBus()
    bus.subscribe("*", make_event_log_handler(session_factory))
    registry = build_observable_registry()

    result = run_observation_sweep(db_session, bus, registry, company.id)

    # Two anomalies (margin on the product, delivery on its own supplier),
    # but they get merged into ONE Business Event, not two, because they
    # share a real link (the product's supplier_id).
    assert result["anomalies_detected"] == 2
    assert result["business_events_published"] == 1

    entry = db_session.query(EventLogEntry).filter_by(event_type=OBSERVATION_DETECTED).one()
    assert entry.payload["observable"] == "margin_pct"
    assert len(entry.payload["correlated_observations"]) == 1
    assert entry.payload["correlated_observations"][0]["observable"] == "delivery_delay_days"
    assert entry.payload["correlated_observations"][0]["entity_name"] == "Northline"
