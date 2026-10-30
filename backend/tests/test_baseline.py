from datetime import datetime, timedelta, timezone

from app.core.baseline import (
    GENERIC_BENCHMARKS,
    build_baseline,
    customer_value_baseline,
    margin_baseline,
    supplier_delivery_baseline,
)
from app.core.entities import (
    BusinessContext,
    Company,
    Customer,
    Product,
    Supplier,
    Transaction,
    TransactionStatus,
    TransactionType,
)


def test_build_baseline_prefers_declared_over_observed():
    baseline = build_baseline("margin_pct", observed_value=0.15, sample_size=8, declared_value=0.30)

    assert baseline.source == "declared"
    assert baseline.confidence == "high"
    assert baseline.reference_value == 0.30  # not the observed 0.15


def test_build_baseline_falls_back_to_generic_when_nothing_else_is_known():
    baseline = build_baseline("margin_pct", observed_value=None, sample_size=0, declared_value=None)

    assert baseline.source == "generic_fallback"
    assert baseline.confidence == "low"
    assert baseline.reference_value == GENERIC_BENCHMARKS["margin_pct"]


def test_build_baseline_confidence_scales_with_sample_size():
    low = build_baseline("margin_pct", observed_value=0.2, sample_size=2)
    medium = build_baseline("margin_pct", observed_value=0.2, sample_size=5)
    high = build_baseline("margin_pct", observed_value=0.2, sample_size=12)

    assert low.confidence == "low"
    assert medium.confidence == "medium"
    assert high.confidence == "high"
    assert low.source == medium.source == high.source == "observed_history"


def test_margin_baseline_uses_declared_value_from_business_context(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()
    supplier = Supplier(company_id=company.id, name="Northline")
    db_session.add(supplier)
    db_session.flush()
    product = Product(company_id=company.id, supplier_id=supplier.id, name="Frame", sku="F-1")
    db_session.add(product)
    db_session.flush()
    context = BusinessContext(company_id=company.id, declared_baselines={"margin_pct": 0.30})
    db_session.add(context)
    db_session.commit()

    baseline, current_value = margin_baseline(db_session, product.id, business_context=context)

    assert baseline.source == "declared"
    assert baseline.reference_value == 0.30
    assert current_value is None  # no transactions seeded for this product


def test_supplier_delivery_baseline_reflects_real_history(db_session):
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

    baseline, current_value = supplier_delivery_baseline(db_session, supplier.id)

    assert baseline.source == "observed_history"
    assert baseline.observed_value == 1.0  # the historical baseline, not the recent value
    assert current_value == 5.0  # the recent value, to be compared against the baseline
    assert baseline.confidence == "medium"  # exactly 4 rows -> medium confidence band


def test_customer_value_baseline_insufficient_data_uses_generic_fallback(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()
    customer = Customer(company_id=company.id, name="New Co")
    db_session.add(customer)
    db_session.commit()

    baseline, current_value = customer_value_baseline(db_session, customer.id)

    assert baseline.source == "generic_fallback"
    assert baseline.confidence == "low"
    assert baseline.reference_value == GENERIC_BENCHMARKS["customer_revenue_variation_pct"]
    assert current_value is None
