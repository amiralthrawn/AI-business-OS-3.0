from datetime import datetime, timedelta, timezone

from app.core.entities import (
    Company,
    Customer,
    EventLogEntry,
    Opportunity,
    Product,
    Risk,
    RiskSeverity,
    Supplier,
    Transaction,
    TransactionStatus,
    TransactionType,
)
from app.core.events.bus import InProcessEventBus
from app.core.events.log_handler import make_event_log_handler
from app.intelligence.monitoring import run_monitoring_sweep
from app.intelligence.opportunities.service import OPPORTUNITY_CREATED, OpportunityDetectionService
from app.intelligence.risks.service import (
    MARGIN_DETERIORATED,
    RISK_CREATED,
    SUPPLIER_PERFORMANCE_DETERIORATED,
    RiskDetectionService,
)


def _company(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()
    return company


def _bus_with_log(session_factory):
    bus = InProcessEventBus()
    bus.subscribe("*", make_event_log_handler(session_factory))
    return bus


def test_margin_deterioration_creates_a_risk_and_is_idempotent(db_session, session_factory):
    company = _company(db_session)
    supplier = Supplier(company_id=company.id, name="Northline Steel")
    db_session.add(supplier)
    db_session.flush()
    customer = Customer(company_id=company.id, name="Buyer Co")
    db_session.add(customer)
    db_session.flush()
    product = Product(company_id=company.id, supplier_id=supplier.id, name="Frame", sku="F-1", unit_cost=420.0)
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

    bus = _bus_with_log(session_factory)
    service = RiskDetectionService(db_session, bus)

    first = service.evaluate_margin_trend(product.id)
    second = service.evaluate_margin_trend(product.id)

    assert first is not None
    assert second is None  # idempotent: an OPEN risk of this kind already exists
    assert db_session.query(Risk).filter_by(related_entity_id=product.id).count() == 1

    event_types = {e.event_type for e in db_session.query(EventLogEntry).all()}
    assert MARGIN_DETERIORATED in event_types
    assert RISK_CREATED in event_types


def test_supplier_performance_deterioration_creates_a_high_severity_risk(db_session, event_bus):
    company = _company(db_session)
    supplier = Supplier(company_id=company.id, name="Iberia Logistics Parts")
    db_session.add(supplier)
    db_session.flush()
    product = Product(company_id=company.id, supplier_id=supplier.id, name="Hose", sku="H-1", unit_cost=27.0)
    db_session.add(product)
    db_session.flush()

    now = datetime.now(timezone.utc)
    for i, delay in enumerate([1.0, 1.0, 5.0, 5.0]):
        occurred_at = now - timedelta(days=(4 - i) * 30)
        db_session.add(
            Transaction(
                company_id=company.id, supplier_id=supplier.id, product_id=product.id,
                type=TransactionType.PURCHASE_ORDER, status=TransactionStatus.CONFIRMED,
                amount=100.0, currency="EUR", occurred_at=occurred_at,
                expected_at=occurred_at - timedelta(days=delay),
            )
        )
    db_session.commit()

    risk = RiskDetectionService(db_session, event_bus).evaluate_supplier_delivery_performance(supplier.id)

    assert risk is not None
    assert risk.severity == RiskSeverity.HIGH
    assert "Iberia Logistics Parts" in risk.title


def test_customer_decline_and_growth_are_mutually_exclusive(db_session, event_bus):
    company = _company(db_session)
    declining = Customer(company_id=company.id, name="Declining Co")
    growing = Customer(company_id=company.id, name="Growing Co")
    db_session.add_all([declining, growing])
    db_session.flush()
    product = Product(company_id=company.id, name="Widget", sku="W-1")
    db_session.add(product)
    db_session.flush()

    now = datetime.now(timezone.utc)
    for i, amount in enumerate([2000.0, 2000.0, 500.0, 500.0]):
        db_session.add(
            Transaction(
                company_id=company.id, customer_id=declining.id, product_id=product.id,
                type=TransactionType.SALES_ORDER, status=TransactionStatus.CONFIRMED,
                amount=amount, currency="EUR", occurred_at=now - timedelta(days=(4 - i) * 30),
            )
        )
    for i, amount in enumerate([1000.0, 1000.0, 2000.0, 2000.0]):
        db_session.add(
            Transaction(
                company_id=company.id, customer_id=growing.id, product_id=product.id,
                type=TransactionType.SALES_ORDER, status=TransactionStatus.CONFIRMED,
                amount=amount, currency="EUR", occurred_at=now - timedelta(days=(4 - i) * 30),
            )
        )
    db_session.commit()

    risk_service = RiskDetectionService(db_session, event_bus)
    opportunity_service = OpportunityDetectionService(db_session, event_bus)

    assert risk_service.evaluate_customer_decline(declining.id) is not None
    assert risk_service.evaluate_customer_decline(growing.id) is None
    assert opportunity_service.evaluate_customer_growth(growing.id) is not None
    assert opportunity_service.evaluate_customer_growth(declining.id) is None


def test_opportunity_created_is_persisted_and_idempotent(db_session, session_factory):
    company = _company(db_session)
    customer = Customer(company_id=company.id, name="Growing Co")
    db_session.add(customer)
    db_session.flush()
    product = Product(company_id=company.id, name="Widget", sku="W-1")
    db_session.add(product)
    db_session.flush()

    now = datetime.now(timezone.utc)
    for i, amount in enumerate([1000.0, 1000.0, 2000.0, 2000.0]):
        db_session.add(
            Transaction(
                company_id=company.id, customer_id=customer.id, product_id=product.id,
                type=TransactionType.SALES_ORDER, status=TransactionStatus.CONFIRMED,
                amount=amount, currency="EUR", occurred_at=now - timedelta(days=(4 - i) * 30),
            )
        )
    db_session.commit()

    bus = _bus_with_log(session_factory)
    service = OpportunityDetectionService(db_session, bus)

    first = service.evaluate_customer_growth(customer.id)
    second = service.evaluate_customer_growth(customer.id)

    assert first is not None
    assert second is None
    assert db_session.query(Opportunity).count() == 1

    event_types = {e.event_type for e in db_session.query(EventLogEntry).all()}
    assert OPPORTUNITY_CREATED in event_types


def test_stable_entities_trigger_no_risk_or_opportunity(db_session, event_bus):
    """The 'ignore routine' principle: a customer with a flat order pattern
    must not produce any Risk or Opportunity."""

    company = _company(db_session)
    customer = Customer(company_id=company.id, name="Stable Co")
    db_session.add(customer)
    db_session.flush()
    product = Product(company_id=company.id, name="Widget", sku="W-1")
    db_session.add(product)
    db_session.flush()

    now = datetime.now(timezone.utc)
    for i in range(4):
        db_session.add(
            Transaction(
                company_id=company.id, customer_id=customer.id, product_id=product.id,
                type=TransactionType.SALES_ORDER, status=TransactionStatus.CONFIRMED,
                amount=1000.0, currency="EUR", occurred_at=now - timedelta(days=(4 - i) * 30),
            )
        )
    db_session.commit()

    risk_service = RiskDetectionService(db_session, event_bus)
    opportunity_service = OpportunityDetectionService(db_session, event_bus)

    assert risk_service.evaluate_customer_decline(customer.id) is None
    assert opportunity_service.evaluate_customer_growth(customer.id) is None
    assert db_session.query(Risk).count() == 0
    assert db_session.query(Opportunity).count() == 0


def test_monitoring_sweep_endpoint_is_idempotent(db_session, session_factory):
    from app.database import get_db
    from app.dependencies import get_event_bus
    from app.event_bus import build_event_bus
    from app.main import app
    from fastapi.testclient import TestClient
    from data.seed import seed

    seed(db_session, build_event_bus(session_factory))
    risks_after_seed = db_session.query(Risk).count()
    opportunities_after_seed = db_session.query(Opportunity).count()

    def override_get_db():
        yield db_session

    def override_get_event_bus():
        return build_event_bus(session_factory)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_event_bus] = override_get_event_bus
    try:
        response = TestClient(app).post("/intelligence/monitor")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"risks_created": 0, "opportunities_created": 0}
    assert db_session.query(Risk).count() == risks_after_seed
    assert db_session.query(Opportunity).count() == opportunities_after_seed
