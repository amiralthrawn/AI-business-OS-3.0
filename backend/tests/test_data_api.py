"""Step 23B: the Business Domain read APIs (Supplier/Customer/Product/
Transaction, list + detail). Every non-trivial field is composed from an
already-existing function (get_entity_context, app.core.analytics,
HomeService.get_ai_priorities) -- these tests check the composition and the
HTTP surface, not a second implementation of any of them."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.entities import (
    Company,
    Customer,
    Product,
    RelatedEntityType,
    Risk,
    RiskSeverity,
    RiskStatus,
    Supplier,
    Transaction,
    TransactionStatus,
    TransactionType,
)
from app.database import get_db
from app.main import app


def _client_with(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _seed_minimal_company(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()
    supplier = Supplier(company_id=company.id, name="Northline Steel", country="DE")
    db_session.add(supplier)
    db_session.flush()
    product = Product(company_id=company.id, supplier_id=supplier.id, name="Steel Frame", sku="STL-1", unit_cost=100.0)
    db_session.add(product)
    db_session.flush()
    customer = Customer(company_id=company.id, name="Metroline Corp", country="FR")
    db_session.add(customer)
    db_session.flush()

    now = datetime.now(timezone.utc)
    db_session.add(
        Transaction(
            company_id=company.id, supplier_id=supplier.id, product_id=product.id,
            type=TransactionType.PURCHASE_ORDER, status=TransactionStatus.CONFIRMED,
            amount=500.0, currency="EUR", occurred_at=now - timedelta(days=10),
        )
    )
    db_session.add(
        Transaction(
            company_id=company.id, customer_id=customer.id, product_id=product.id,
            type=TransactionType.SALES_ORDER, status=TransactionStatus.CONFIRMED,
            amount=900.0, currency="EUR", occurred_at=now - timedelta(days=5),
        )
    )
    db_session.commit()
    return company, supplier, product, customer


# --- Suppliers ----------------------------------------------------------------


def test_list_suppliers_returns_basic_fields(db_session):
    company, supplier, product, customer = _seed_minimal_company(db_session)

    client = _client_with(db_session)
    try:
        response = client.get("/suppliers")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "Northline Steel"
    assert body[0]["product_count"] == 1
    assert body[0]["transaction_count"] == 1


def test_get_supplier_detail_exposes_relations(db_session):
    company, supplier, product, customer = _seed_minimal_company(db_session)
    db_session.add(
        Risk(
            company_id=company.id, title="Test risk", severity=RiskSeverity.HIGH, status=RiskStatus.OPEN,
            related_entity_type=__import__("app.core.entities", fromlist=["RelatedEntityType"]).RelatedEntityType.SUPPLIER,
            related_entity_id=supplier.id,
        )
    )
    db_session.commit()

    client = _client_with(db_session)
    try:
        response = client.get(f"/suppliers/{supplier.id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(supplier.id)
    assert body["name"] == "Northline Steel"
    assert body["country"] == "DE"
    assert [p["name"] for p in body["products"]] == ["Steel Frame"]
    assert len(body["transactions"]) == 1
    assert [r["title"] for r in body["open_risks"]] == ["Test risk"]
    assert "delivery_trend" in body
    assert "unanswered_message_age_days" in body


def test_get_unknown_supplier_returns_404(db_session):
    company, supplier, product, customer = _seed_minimal_company(db_session)

    client = _client_with(db_session)
    try:
        response = client.get("/suppliers/00000000-0000-0000-0000-000000000000")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


# --- Customers ------------------------------------------------------------


def test_list_and_get_customer(db_session):
    company, supplier, product, customer = _seed_minimal_company(db_session)

    client = _client_with(db_session)
    try:
        list_response = client.get("/customers")
        detail_response = client.get(f"/customers/{customer.id}")
    finally:
        app.dependency_overrides.clear()

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["name"] == "Metroline Corp"

    assert detail_response.status_code == 200
    body = detail_response.json()
    assert body["name"] == "Metroline Corp"
    assert body["country"] == "FR"
    assert len(body["transactions"]) == 1
    assert "revenue_trend" in body


# --- Products ---------------------------------------------------------------


def test_list_and_get_product(db_session):
    company, supplier, product, customer = _seed_minimal_company(db_session)

    client = _client_with(db_session)
    try:
        list_response = client.get("/products")
        detail_response = client.get(f"/products/{product.id}")
    finally:
        app.dependency_overrides.clear()

    assert list_response.status_code == 200
    assert list_response.json()[0]["supplier"]["name"] == "Northline Steel"

    assert detail_response.status_code == 200
    body = detail_response.json()
    assert body["sku"] == "STL-1"
    assert body["unit_cost"] == 100.0
    assert body["supplier"]["id"] == str(supplier.id)
    assert len(body["transactions"]) == 2  # both the PO and the sales order
    assert "margin_trend" in body


# --- Transactions -------------------------------------------------------------


def test_list_and_get_transaction(db_session):
    company, supplier, product, customer = _seed_minimal_company(db_session)
    transaction = db_session.query(Transaction).filter_by(type=TransactionType.SALES_ORDER).one()

    client = _client_with(db_session)
    try:
        list_response = client.get("/transactions")
        detail_response = client.get(f"/transactions/{transaction.id}")
    finally:
        app.dependency_overrides.clear()

    assert list_response.status_code == 200
    assert len(list_response.json()) == 2

    assert detail_response.status_code == 200
    body = detail_response.json()
    assert body["type"] == "sales_order"
    assert body["customer_name"] == "Metroline Corp"
    assert body["product_name"] == "Steel Frame"


# --- Company scoping ----------------------------------------------------------


def test_suppliers_do_not_leak_across_companies(db_session):
    company_a, supplier_a, product_a, customer_a = _seed_minimal_company(db_session)

    company_b = Company(name="Other Co")
    db_session.add(company_b)
    db_session.flush()
    supplier_b = Supplier(company_id=company_b.id, name="Other Supplier")
    db_session.add(supplier_b)
    db_session.commit()

    client = _client_with(db_session)
    try:
        # The routers assume single-company (db.query(Company).first()),
        # matching every other router in this codebase -- so only the
        # first-created company's own data is ever returned.
        list_response = client.get("/suppliers")
        other_detail_response = client.get(f"/suppliers/{supplier_b.id}")
    finally:
        app.dependency_overrides.clear()

    names = {s["name"] for s in list_response.json()}
    assert "Other Supplier" not in names
    assert other_detail_response.status_code == 404


# --- Intelligence surfaced in a domain view ------------------------------------


def test_supplier_detail_surfaces_a_material_intelligence_signal(db_session, session_factory):
    from app.business_context.service import BusinessContextService
    from app.core.events.bus import InProcessEventBus
    from app.core.events.log_handler import make_event_log_handler
    from app.intelligence.risks.service import RiskDetectionService

    bus = InProcessEventBus()
    bus.subscribe("*", make_event_log_handler(session_factory))

    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()
    BusinessContextService(db_session).get_or_create(company.id)
    supplier = Supplier(company_id=company.id, name="Iberia Logistics")
    db_session.add(supplier)
    db_session.flush()
    product = Product(company_id=company.id, supplier_id=supplier.id, name="Hose", sku="H-1")
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
    RiskDetectionService(db_session, bus).evaluate_supplier_delivery_performance(supplier.id)

    client = _client_with(db_session)
    try:
        response = client.get(f"/suppliers/{supplier.id}")
    finally:
        app.dependency_overrides.clear()

    body = response.json()
    assert len(body["intelligence"]) == 1
    assert body["intelligence"][0]["kind"] == "risk"
    assert "Iberia Logistics" in body["intelligence"][0]["title"]
