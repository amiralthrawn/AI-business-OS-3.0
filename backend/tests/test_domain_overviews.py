"""Step 23B: the Finance/Procurement/Sales domain overview endpoints. Each
one is composed entirely from app.data.service (list_suppliers/list_customers/
list_transactions) and app.core.analytics.compute_company_financials -- these
tests check the composition and the HTTP surface, not a second implementation
of any of them."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.entities import (
    Company,
    Customer,
    Product,
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


def _seed_company_with_financials(db_session):
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


def test_finance_overview_aggregates_real_transactions(db_session):
    _seed_company_with_financials(db_session)

    client = _client_with(db_session)
    try:
        response = client.get("/finance/overview")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["total_revenue"] == 900.0
    assert body["total_costs"] == 500.0
    assert body["overall_margin_pct"] == (900.0 - 500.0) / 900.0
    assert body["transaction_count"] == 2
    assert len(body["recent_transactions"]) == 2


def test_procurement_overview_lists_suppliers_and_spend(db_session):
    _seed_company_with_financials(db_session)

    client = _client_with(db_session)
    try:
        response = client.get("/procurement/overview")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["supplier_count"] == 1
    assert body["suppliers"][0]["name"] == "Northline Steel"
    assert body["total_spend"] == 500.0
    assert len(body["recent_transactions"]) == 1  # only the supplier-side PO, not the sales order


def test_sales_overview_lists_customers_and_revenue(db_session):
    _seed_company_with_financials(db_session)

    client = _client_with(db_session)
    try:
        response = client.get("/sales/overview")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["customer_count"] == 1
    assert body["customers"][0]["name"] == "Metroline Corp"
    assert body["total_revenue"] == 900.0
    assert len(body["recent_transactions"]) == 1  # only the customer-side sales order


def test_domain_overviews_are_empty_but_not_broken_with_no_company(db_session):
    client = _client_with(db_session)
    try:
        finance = client.get("/finance/overview")
        procurement = client.get("/procurement/overview")
        sales = client.get("/sales/overview")
    finally:
        app.dependency_overrides.clear()

    for response in (finance, procurement, sales):
        assert response.status_code == 200
