"""Context Assembly (app.interpretation.context): proof that the context
handed to the LLM is compact (a handful of known keys, never the whole Data
Core) and that it consults the same targeted AI capabilities a named Ask AI
question about the same entity would have used."""

from datetime import datetime, timedelta, timezone

from app.ai.capabilities import build_capability_registry
from app.ai.llm import DeterministicLLMClient
from app.business_context.service import BusinessContextService
from app.core.entities import (
    Company,
    Customer,
    EventLogEntry,
    Product,
    Supplier,
    Transaction,
    TransactionStatus,
    TransactionType,
)
from app.core.events.bus import InProcessEventBus
from app.core.events.log_handler import make_event_log_handler
from app.interpretation.context import assemble_context
from app.observation import build_observable_registry
from app.observation.engine import OBSERVATION_DETECTED, run_observation_sweep


def _bus(session_factory):
    bus = InProcessEventBus()
    bus.subscribe("*", make_event_log_handler(session_factory))
    return bus


def _seed_margin_scenario(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()
    BusinessContextService(db_session).update(company.id, declared_baselines={"margin_pct": 0.30})

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
    return company, supplier, product, customer


def _observation_entry(db_session):
    return db_session.query(EventLogEntry).filter_by(event_type=OBSERVATION_DETECTED).one()


def test_assemble_context_is_compact_and_carries_the_key_layers(db_session, session_factory):
    bus = _bus(session_factory)
    company, supplier, product, customer = _seed_margin_scenario(db_session)
    run_observation_sweep(db_session, bus, build_observable_registry(), company.id)
    entry = _observation_entry(db_session)

    context, _ = assemble_context(db_session, bus, build_capability_registry(), DeterministicLLMClient(), company.id, entry)

    assert context["business_event"]["observable"] == "margin_pct"
    assert context["business_event"]["entity_name"] == "Frame"
    assert context["baseline"]["source"] == "declared"
    assert context["baseline"]["confidence"] == "high"
    assert context["significance"]["impact"] == "high"
    assert context["snapshot_summary"]["open_risks_count"] == 0
    assert context["business_context"]["declared_baseline_for_this_metric"] == 0.30

    # Compact: only these known layers, never a dump of the whole Data Core.
    assert set(context.keys()) <= {
        "business_event", "baseline", "significance", "correlated_observations",
        "related_messages_from_correlated_observations",
        "business_context", "snapshot_summary", "capability_data",
    }


def test_assemble_context_consults_the_domains_targeted_capabilities(db_session, session_factory):
    bus = _bus(session_factory)
    company, supplier, product, customer = _seed_margin_scenario(db_session)
    run_observation_sweep(db_session, bus, build_observable_registry(), company.id)
    entry = _observation_entry(db_session)

    context, capabilities_consulted = assemble_context(
        db_session, bus, build_capability_registry(), DeterministicLLMClient(), company.id, entry
    )

    # The event's domain is "finance" -> finance_agent's own capabilities,
    # applied to the Product this margin anomaly is about -- the exact same
    # dispatch a human's "what's our margin on Frame?" question would use.
    assert "analyze_margin" in capabilities_consulted
    assert "read_transactions" in capabilities_consulted
    assert "capability_data" in context
    assert "analyze_margin" in context["capability_data"]
