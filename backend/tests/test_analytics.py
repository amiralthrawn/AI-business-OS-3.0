from datetime import datetime, timedelta, timezone

from app.core.analytics import (
    compute_customer_value_trend,
    compute_margin_trend,
    compute_monthly_series,
    compute_supplier_delivery_performance,
)
from app.core.entities import Company, Customer, Product, Supplier, Transaction, TransactionStatus, TransactionType


def _base(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()
    return company


def test_supplier_delivery_performance_detects_deterioration(db_session):
    company = _base(db_session)
    supplier = Supplier(company_id=company.id, name="Iberia")
    db_session.add(supplier)
    db_session.flush()
    product = Product(company_id=company.id, supplier_id=supplier.id, name="Hose", sku="H-1", unit_cost=27.0)
    db_session.add(product)
    db_session.flush()

    now = datetime.now(timezone.utc)
    delays = [1.0, 1.0, 5.0, 5.0]
    for i, delay in enumerate(delays):
        occurred_at = now - timedelta(days=(len(delays) - i) * 30)
        db_session.add(
            Transaction(
                company_id=company.id,
                supplier_id=supplier.id,
                product_id=product.id,
                type=TransactionType.PURCHASE_ORDER,
                status=TransactionStatus.CONFIRMED,
                amount=100.0,
                currency="EUR",
                occurred_at=occurred_at,
                expected_at=occurred_at - timedelta(days=delay),
            )
        )
    db_session.commit()

    result = compute_supplier_delivery_performance(db_session, supplier.id)

    assert result.trend == "deteriorating"
    assert result.recent_avg_delay_days == 5.0
    assert result.baseline_avg_delay_days == 1.0


def test_monthly_series_is_real_and_zero_filled(db_session):
    company = _base(db_session)
    supplier = Supplier(company_id=company.id, name="Iberia")
    db_session.add(supplier)
    db_session.flush()
    product = Product(company_id=company.id, supplier_id=supplier.id, name="Hose", sku="H-1", unit_cost=27.0)
    db_session.add(product)
    db_session.flush()

    now = datetime.now(timezone.utc)
    # Two Purchase Orders this calendar month, none last month, one two months ago.
    db_session.add_all(
        [
            Transaction(
                company_id=company.id, supplier_id=supplier.id, product_id=product.id,
                type=TransactionType.PURCHASE_ORDER, status=TransactionStatus.CONFIRMED,
                amount=100.0, currency="EUR", occurred_at=now,
            ),
            Transaction(
                company_id=company.id, supplier_id=supplier.id, product_id=product.id,
                type=TransactionType.PURCHASE_ORDER, status=TransactionStatus.CONFIRMED,
                amount=50.0, currency="EUR", occurred_at=now - timedelta(days=1),
            ),
            Transaction(
                company_id=company.id, supplier_id=supplier.id, product_id=product.id,
                type=TransactionType.PURCHASE_ORDER, status=TransactionStatus.CONFIRMED,
                amount=200.0, currency="EUR", occurred_at=now - timedelta(days=65),
            ),
        ]
    )
    db_session.commit()

    series = compute_monthly_series(db_session, company.id, [TransactionType.PURCHASE_ORDER], months=12, now=now)

    by_month = {point.month: point for point in series}
    older = now - timedelta(days=65)

    assert len(series) == 12
    assert by_month[f"{now.year:04d}-{now.month:02d}"].total_amount == 150.0
    assert by_month[f"{now.year:04d}-{now.month:02d}"].transaction_count == 2
    assert by_month[f"{older.year:04d}-{older.month:02d}"].total_amount == 200.0
    # A month with no matching Transaction is explicitly zero, not omitted.
    untouched_months = [m for m in by_month if m not in (f"{now.year:04d}-{now.month:02d}", f"{older.year:04d}-{older.month:02d}")]
    assert untouched_months  # there is at least one such month in a 12-month window
    assert all(by_month[m].total_amount == 0.0 and by_month[m].transaction_count == 0 for m in untouched_months)


def test_supplier_delivery_performance_insufficient_data(db_session):
    company = _base(db_session)
    supplier = Supplier(company_id=company.id, name="Iberia")
    db_session.add(supplier)
    db_session.commit()

    result = compute_supplier_delivery_performance(db_session, supplier.id)

    assert result.trend == "insufficient_data"
    assert result.recent_avg_delay_days is None


def test_customer_value_trend_detects_growth_and_decline(db_session):
    company = _base(db_session)
    growing = Customer(company_id=company.id, name="Growing Co")
    declining = Customer(company_id=company.id, name="Declining Co")
    db_session.add_all([growing, declining])
    db_session.flush()
    product = Product(company_id=company.id, name="Widget", sku="W-1")
    db_session.add(product)
    db_session.flush()

    now = datetime.now(timezone.utc)
    for i, amount in enumerate([1000.0, 1000.0, 2000.0, 2000.0]):
        db_session.add(
            Transaction(
                company_id=company.id,
                customer_id=growing.id,
                product_id=product.id,
                type=TransactionType.SALES_ORDER,
                status=TransactionStatus.CONFIRMED,
                amount=amount,
                currency="EUR",
                occurred_at=now - timedelta(days=(4 - i) * 30),
            )
        )
    for i, amount in enumerate([2000.0, 2000.0, 500.0, 500.0]):
        db_session.add(
            Transaction(
                company_id=company.id,
                customer_id=declining.id,
                product_id=product.id,
                type=TransactionType.SALES_ORDER,
                status=TransactionStatus.CONFIRMED,
                amount=amount,
                currency="EUR",
                occurred_at=now - timedelta(days=(4 - i) * 30),
            )
        )
    db_session.commit()

    growth = compute_customer_value_trend(db_session, growing.id)
    decline = compute_customer_value_trend(db_session, declining.id)

    assert growth.trend == "growing"
    assert decline.trend == "declining"


def test_margin_trend_deteriorates_when_cost_outpaces_revenue(db_session):
    company = _base(db_session)
    supplier = Supplier(company_id=company.id, name="Steel Co")
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
                company_id=company.id,
                supplier_id=supplier.id,
                product_id=product.id,
                type=TransactionType.PURCHASE_ORDER,
                status=TransactionStatus.CONFIRMED,
                amount=cost,
                currency="EUR",
                occurred_at=now - timedelta(days=(4 - i) * 30),
            )
        )
    for i in range(4):
        db_session.add(
            Transaction(
                company_id=company.id,
                customer_id=customer.id,
                product_id=product.id,
                type=TransactionType.SALES_ORDER,
                status=TransactionStatus.CONFIRMED,
                amount=1000.0,
                currency="EUR",
                occurred_at=now - timedelta(days=(4 - i) * 30),
            )
        )
    db_session.commit()

    result = compute_margin_trend(db_session, product.id)

    assert result.trend == "deteriorating"
    assert result.point_change < 0


def test_margin_trend_insufficient_data_without_revenue(db_session):
    company = _base(db_session)
    product = Product(company_id=company.id, name="Widget", sku="W-2")
    db_session.add(product)
    db_session.commit()

    result = compute_margin_trend(db_session, product.id)

    assert result.trend == "insufficient_data"
