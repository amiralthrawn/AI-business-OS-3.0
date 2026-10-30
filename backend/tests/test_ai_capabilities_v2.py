import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.ai.capabilities.analyze_customer_value import analyze_customer_value_capability
from app.ai.capabilities.analyze_supplier_performance import analyze_supplier_performance_capability
from app.ai.capabilities.base import CapabilityExecutionError
from app.ai.capabilities.list_priorities import list_priorities_capability
from app.ai.capabilities.read_customer import read_customer_capability
from app.core.entities import (
    Company,
    Customer,
    Product,
    Risk,
    RiskSeverity,
    RiskStatus,
    Supplier,
    Transaction,
    TransactionStatus,
    TransactionType,
)


def test_read_customer_returns_real_data(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()
    customer = Customer(company_id=company.id, name="Metroline Corp", country="FR")
    db_session.add(customer)
    db_session.commit()

    result = read_customer_capability.run(db_session, customer_id=customer.id)

    assert result.name == "Metroline Corp"
    assert result.country == "FR"


def test_read_customer_missing_raises_clean_error(db_session):
    with pytest.raises(CapabilityExecutionError):
        read_customer_capability.run(db_session, customer_id=uuid.uuid4())


def test_analyze_customer_value_reflects_real_transactions(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()
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

    result = analyze_customer_value_capability.run(db_session, customer_id=customer.id)

    assert result.trend == "growing"
    assert result.baseline_revenue == 2000.0
    assert result.recent_revenue == 4000.0


def test_analyze_supplier_performance_reflects_real_transactions(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()
    supplier = Supplier(company_id=company.id, name="Iberia")
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

    result = analyze_supplier_performance_capability.run(db_session, supplier_id=supplier.id)

    assert result.trend == "deteriorating"
    assert result.recent_avg_delay_days == 5.0


def test_list_priorities_reflects_real_open_risks_and_opportunities(db_session, event_bus):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()
    db_session.add(
        Risk(
            company_id=company.id,
            title="Margin deterioration on product Frame",
            severity=RiskSeverity.HIGH,
            status=RiskStatus.OPEN,
        )
    )
    db_session.commit()

    result = list_priorities_capability.run(db_session, event_bus=event_bus)

    assert result.total_open_risks == 1
    assert len(result.priorities) == 1
    assert result.priorities[0].kind == "risk"
    assert result.priorities[0].severity == "high"
