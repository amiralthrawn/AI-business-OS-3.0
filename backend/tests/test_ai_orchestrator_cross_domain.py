"""Step 18: the AI Orchestrator's cross-domain reasoning for a question that
names no specific supplier/product/customer (e.g. "Why is our margin
declining?"). Covers: a genuinely multi-domain question aggregating several
capabilities across several significant entities, an insufficient-context
question, that the Orchestrator never scans the whole Data Core (only what
the Snapshot already flagged as material), and that the pre-existing
single-domain / named-entity / broad-priorities behaviors are unaffected."""

from datetime import datetime, timedelta, timezone

import pytest

from app.ai.capabilities import build_capability_registry
from app.ai.llm import DeterministicLLMClient
from app.ai.orchestrator import AIOrchestrator, OrchestratorError
from app.business_context.service import BusinessContextService
from app.core.entities import (
    Company,
    Customer,
    Product,
    Supplier,
    Transaction,
    TransactionStatus,
    TransactionType,
)


def _orchestrator(db_session, event_bus):
    return AIOrchestrator(db_session, build_capability_registry(), DeterministicLLMClient(), event_bus)


def _seed_margin_only_risk(db_session, event_bus):
    """A single, real Margin deterioration Risk (finance domain) -- for a
    cross-domain-eligible question ("margin" matches finance+procurement+
    sales) that in practice only has ONE significant area to draw from."""

    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()
    BusinessContextService(db_session).get_or_create(company.id)

    supplier = Supplier(company_id=company.id, name="Northline Steel")
    db_session.add(supplier)
    db_session.flush()
    customer = Customer(company_id=company.id, name="Buyer Co")
    db_session.add(customer)
    db_session.flush()
    product = Product(company_id=company.id, supplier_id=supplier.id, name="Steel Frame Assembly", sku="STL-1")
    db_session.add(product)
    db_session.flush()

    now = datetime.now(timezone.utc)
    for i, cost in enumerate([400.0, 400.0, 900.0, 900.0]):
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

    from app.intelligence.risks.service import RiskDetectionService

    RiskDetectionService(db_session, event_bus).evaluate_margin_trend(product.id)
    return company, supplier, product, customer


def _seed_two_domain_scenario(db_session, event_bus):
    """Two real, unrelated Risks in two different domains -- finance (margin
    on Steel Frame Assembly) and procurement (delivery performance on Iberia
    Logistics) -- so a "margin" question genuinely has significant areas in
    2+ domains to aggregate, each needing its own capability calls."""

    company, supplier, product, customer = _seed_margin_only_risk(db_session, event_bus)

    iberia = Supplier(company_id=company.id, name="Iberia Logistics")
    db_session.add(iberia)
    db_session.flush()
    hose = Product(company_id=company.id, supplier_id=iberia.id, name="Hydraulic Hose", sku="HYD-1")
    db_session.add(hose)
    db_session.flush()

    now = datetime.now(timezone.utc)
    for i, delay in enumerate([1.0, 1.0, 5.0, 5.0]):
        occurred_at = now - timedelta(days=(4 - i) * 30)
        db_session.add(
            Transaction(
                company_id=company.id, supplier_id=iberia.id, product_id=hose.id,
                type=TransactionType.PURCHASE_ORDER, status=TransactionStatus.CONFIRMED,
                amount=100.0, currency="EUR", occurred_at=occurred_at,
                expected_at=occurred_at - timedelta(days=delay),
            )
        )
    db_session.commit()

    from app.intelligence.risks.service import RiskDetectionService

    RiskDetectionService(db_session, event_bus).evaluate_supplier_delivery_performance(iberia.id)
    return company, supplier, product, customer, iberia, hose


# --- 1. Mono-domain question (unaffected by this step) -----------------------


def test_mono_domain_question_still_routes_to_a_single_agent(db_session, event_bus):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()
    customer = Customer(company_id=company.id, name="Metroline Corp")
    db_session.add(customer)
    db_session.commit()

    result = _orchestrator(db_session, event_bus).ask("How is customer Metroline Corp doing?")

    assert result.agent == "sales"
    assert "read_customer" in result.capabilities_used
    assert "analyze_customer_value" in result.capabilities_used


# --- 2 & 3. Cross-domain question, no named entity: 2+ domains, several capabilities


def test_cross_domain_question_with_no_named_entity_drills_into_the_significant_area(db_session, event_bus):
    company, supplier, product, customer = _seed_margin_only_risk(db_session, event_bus)

    result = _orchestrator(db_session, event_bus).ask("Why is our margin declining?")

    assert "finance" in result.agent
    assert "procurement" in result.agent
    assert "sales" in result.agent
    assert "get_business_state_snapshot" in result.capabilities_used
    assert "analyze_margin" in result.capabilities_used
    assert "read_transactions" in result.capabilities_used
    assert result.context["get_business_state_snapshot"]["material_areas"]


def test_cross_domain_question_aggregates_two_distinct_domains_and_entities(db_session, event_bus):
    company, supplier, product, customer, iberia, hose = _seed_two_domain_scenario(db_session, event_bus)

    result = _orchestrator(db_session, event_bus).ask("Why is our margin declining?")

    # Two distinct significant areas, in two distinct domains, both
    # contributed real capability calls to a single synthesized answer.
    assert "analyze_margin" in result.capabilities_used
    assert "analyze_supplier_performance" in result.capabilities_used
    assert "read_supplier" in result.capabilities_used

    snapshot = result.context["get_business_state_snapshot"]
    domains_seen = {a["domain"] for a in snapshot["material_areas"]}
    assert {"finance", "procurement"} <= domains_seen

    # Each area's capability results are kept distinct (not clobbered by
    # each other under the same capability-name key).
    area_keys = [k for k in result.context if k != "get_business_state_snapshot"]
    assert len(area_keys) == 2


# --- 4. Insufficient context ---------------------------------------------------


def test_cross_domain_question_with_no_significant_data_raises_a_clean_error(db_session, event_bus):
    # A supplier/product exist, but nothing anomalous was ever detected --
    # the Snapshot has no material areas for the matched domain(s).
    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()
    supplier = Supplier(company_id=company.id, name="Northline Steel")
    db_session.add(supplier)
    db_session.flush()
    db_session.add(Product(company_id=company.id, supplier_id=supplier.id, name="Sensor Module", sku="PCB-011"))
    db_session.commit()

    with pytest.raises(OrchestratorError):
        _orchestrator(db_session, event_bus).ask("Why is our margin declining?")


# --- 5. Never scans the whole Data Core ---------------------------------------


def test_cross_domain_question_only_touches_the_significant_entity_not_every_supplier(db_session, event_bus):
    """Several unrelated, non-anomalous suppliers/products exist alongside
    the one real Risk -- the Orchestrator must only ever gather data for the
    Snapshot's flagged entity, never scan every Supplier/Product/Customer
    in the Data Core."""

    company, supplier, product, customer = _seed_margin_only_risk(db_session, event_bus)

    for i in range(5):
        noise_supplier = Supplier(company_id=company.id, name=f"Unrelated Supplier {i}")
        db_session.add(noise_supplier)
        db_session.flush()
        db_session.add(Product(company_id=company.id, supplier_id=noise_supplier.id, name=f"Unrelated Product {i}", sku=f"NP-{i}"))
    db_session.commit()

    result = _orchestrator(db_session, event_bus).ask("Why is our margin declining?")

    # Only the one real area was consulted -- one area key besides the
    # snapshot summary itself, not six.
    area_keys = [k for k in result.context if k != "get_business_state_snapshot"]
    assert len(area_keys) == 1
    for i in range(5):
        assert f"Unrelated Supplier {i}" not in str(result.context)


# --- 6. The broad "what deserves my attention?" path is unaffected -----------


def test_broad_priorities_question_still_drills_into_the_snapshot_first(db_session, event_bus):
    company, supplier, product, customer = _seed_margin_only_risk(db_session, event_bus)

    result = _orchestrator(db_session, event_bus).ask("What deserves my attention today?")

    assert result.agent == "priorities"
    assert result.capabilities_used[:2] == ["list_priorities", "get_business_state_snapshot"]
    assert result.context["get_business_state_snapshot"]["material_areas"]
    # Still drills into the top area's targeted capabilities, unchanged.
    assert "analyze_margin" in result.capabilities_used
