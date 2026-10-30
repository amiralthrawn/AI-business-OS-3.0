"""Proof that the Snapshot is now fed by the Observation Engine's Business
Events, not only by Risks/Opportunities from the older per-metric rules --
the explicit "progressively fed" requirement for this step."""

from datetime import datetime, timedelta, timezone

from app.business_context.service import BusinessContextService
from app.core.entities import (
    Company,
    Customer,
    Product,
    Risk,
    Supplier,
    Transaction,
    TransactionStatus,
    TransactionType,
)
from app.observation import build_observable_registry
from app.observation.engine import run_observation_sweep
from app.snapshot.service import build_snapshot


def test_snapshot_includes_an_observation_area_not_covered_by_an_existing_risk(db_session, session_factory):
    from app.core.events.bus import InProcessEventBus
    from app.core.events.log_handler import make_event_log_handler

    event_bus = InProcessEventBus()
    event_bus.subscribe("*", make_event_log_handler(session_factory))

    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()
    BusinessContextService(db_session).get_or_create(company.id)

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
    for i, cost in enumerate([400.0, 400.0, 600.0, 600.0]):
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

    # Only the NEW Observation Engine runs here -- no Risk is created by the
    # older per-metric rules (app.intelligence.risks.service is untouched).
    assert db_session.query(Risk).count() == 0
    run_observation_sweep(db_session, event_bus, build_observable_registry(), company.id)

    snapshot = build_snapshot(db_session, company.id)

    observation_areas = [a for a in snapshot.areas if a.kind == "observation"]
    assert len(observation_areas) == 1
    assert observation_areas[0].metric == "margin_pct"
    assert observation_areas[0].significance.is_material is True
    assert observation_areas[0] in snapshot.material_areas


def test_snapshot_does_not_duplicate_an_observation_already_covered_by_a_risk(db_session, session_factory):
    from app.core.events.bus import InProcessEventBus
    from app.core.events.log_handler import make_event_log_handler
    from app.intelligence.risks.service import RiskDetectionService

    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()
    BusinessContextService(db_session).get_or_create(company.id)

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
    for i, cost in enumerate([400.0, 400.0, 600.0, 600.0]):
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

    bus = InProcessEventBus()
    bus.subscribe("*", make_event_log_handler(session_factory))

    # Both the new Observation Engine AND the older per-metric Risk rule fire
    # for the same product.
    run_observation_sweep(db_session, bus, build_observable_registry(), company.id)
    RiskDetectionService(db_session, bus).evaluate_margin_trend(product.id)

    snapshot = build_snapshot(db_session, company.id)

    # Represented once, as a "risk" area (the more specific, already-actioned
    # representation) -- not also duplicated as a separate "observation" area.
    areas_for_product = [a for a in snapshot.areas if a.entity_id == product.id]
    assert len(areas_for_product) == 1
    assert areas_for_product[0].kind == "risk"
