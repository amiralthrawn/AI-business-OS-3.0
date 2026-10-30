import uuid

from fastapi.testclient import TestClient

from app.core.entities import Company, EventLogEntry, Product, Risk, Supplier
from app.database import get_db
from app.dependencies import get_event_bus
from app.event_bus import build_event_bus
from app.main import app


def test_procurement_endpoint_records_cost_increase_and_triggers_the_full_chain(db_session, session_factory):
    company = Company(name="API Co")
    db_session.add(company)
    db_session.flush()
    supplier = Supplier(company_id=company.id, name="API Supplier")
    db_session.add(supplier)
    db_session.flush()
    product = Product(company_id=company.id, supplier_id=supplier.id, name="Gadget", sku="G-1", unit_cost=50.0)
    db_session.add(product)
    db_session.commit()

    def override_get_db():
        yield db_session

    # Reuses the real production wiring (Event Log + Intelligence risk detector)
    # against the isolated test database, instead of a bus with only the log
    # handler -- this is what actually proves the full chain works through the
    # API, not just the Procurement service in isolation.
    def override_get_event_bus():
        return build_event_bus(session_factory)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_event_bus] = override_get_event_bus
    try:
        client = TestClient(app)
        response = client.post(
            "/procurement/supplier-cost-changes",
            json={
                "supplier_id": str(supplier.id),
                "product_id": str(product.id),
                "new_unit_cost": 65.0,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["event_type"] == "SupplierCostIncreased"
    assert body["old_unit_cost"] == 50.0
    assert body["new_unit_cost"] == 65.0
    assert body["variation_pct"] == 0.3

    assert db_session.query(EventLogEntry).filter_by(event_id=uuid.UUID(body["event_id"])).count() == 1

    # A 30% increase clears the risk threshold: the chain should have produced
    # a Risk and a persisted RiskCreated too.
    risk = db_session.query(Risk).filter_by(source_event_id=uuid.UUID(body["event_id"])).one()
    assert risk.related_entity_id == supplier.id
    assert db_session.query(EventLogEntry).filter_by(event_type="RiskCreated").count() == 1


def test_procurement_endpoint_rejects_a_non_increase(db_session, session_factory):
    company = Company(name="API Co 2")
    db_session.add(company)
    db_session.flush()
    supplier = Supplier(company_id=company.id, name="API Supplier 2")
    db_session.add(supplier)
    db_session.flush()
    product = Product(company_id=company.id, supplier_id=supplier.id, name="Gadget 2", sku="G-2", unit_cost=50.0)
    db_session.add(product)
    db_session.commit()

    def override_get_db():
        yield db_session

    def override_get_event_bus():
        return build_event_bus(session_factory)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_event_bus] = override_get_event_bus
    try:
        client = TestClient(app)
        response = client.post(
            "/procurement/supplier-cost-changes",
            json={
                "supplier_id": str(supplier.id),
                "product_id": str(product.id),
                "new_unit_cost": 40.0,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
