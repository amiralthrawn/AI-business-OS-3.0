import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.entities import Communication, CommunicationDirection, Company, EventLogEntry, Product, Supplier
from app.database import get_db
from app.dependencies import get_event_bus
from app.event_bus import build_event_bus
from app.main import app


def test_home_endpoint_returns_200_with_no_data(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).get("/home")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["overview"] == {
        "supplier_count": 0,
        "product_count": 0,
        "customer_count": 0,
        "transaction_count": 0,
    }
    assert body["risks"]["recent_risks"] == []
    assert body["tasks"]["recent_tasks"] == []
    assert body["recent_events"] == []


def test_home_endpoint_reflects_the_full_procurement_to_actions_chain(db_session, session_factory):
    company = Company(name="Home Co")
    db_session.add(company)
    db_session.flush()
    supplier = Supplier(company_id=company.id, name="Home Supplier")
    db_session.add(supplier)
    db_session.flush()
    product = Product(company_id=company.id, supplier_id=supplier.id, name="Widget", sku="H-1", unit_cost=100.0)
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
        procurement_response = client.post(
            "/procurement/supplier-cost-changes",
            json={"supplier_id": str(supplier.id), "product_id": str(product.id), "new_unit_cost": 140.0},
        )
        assert procurement_response.status_code == 200

        home_response = client.get("/home")
    finally:
        app.dependency_overrides.clear()

    assert home_response.status_code == 200
    body = home_response.json()

    assert body["overview"]["supplier_count"] == 1
    assert body["overview"]["product_count"] == 1

    assert body["risks"]["total_risks"] == 1
    assert body["risks"]["recent_risks"][0]["related_entity_id"] == str(supplier.id)

    assert body["tasks"]["total_tasks"] == 1
    assert body["tasks"]["pending_validation_tasks"] == 1
    assert body["tasks"]["recent_tasks"][0]["status"] == "pending_validation"

    event_types = {e["event_type"] for e in body["recent_events"]}
    assert {"SupplierCostIncreased", "RiskCreated", "TaskCreated"} <= event_types


def test_home_activity_endpoint_translates_events_to_french(db_session):
    db_session.add(
        EventLogEntry(
            event_id=uuid.uuid4(), event_type="ObservationDetected", source="observation_engine",
            correlation_id=uuid.uuid4(), occurred_at=datetime.now(timezone.utc),
            payload={"domain": "finance", "observable": "margin_pct", "entity_name": "Steel Frame Assembly"},
        )
    )
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).get("/home/activity")
        filtered_response = TestClient(app).get("/home/activity?domain=sales")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["label"] == "Analyse effectuée"

    assert filtered_response.status_code == 200
    assert filtered_response.json() == []


def test_home_narrative_endpoint_returns_real_communications(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()
    db_session.add(
        Communication(
            company_id=company.id, channel="internal", channel_detail="employee_idea",
            direction=CommunicationDirection.INBOUND, subject="Idée", body="...",
            occurred_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).get("/home/narrative")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["subject"] == "Idée"
