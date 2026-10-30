from datetime import datetime, timedelta, timezone

import pytest

from app.ai.capabilities import build_capability_registry
from app.ai.llm import DeterministicLLMClient
from app.ai.orchestrator import AIOrchestrator, OrchestratorError
from app.core.entities import (
    Company,
    Customer,
    Product,
    Supplier,
    Transaction,
    TransactionStatus,
    TransactionType,
)


def _make_supplier_and_product(db_session, unit_cost=100.0):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()

    supplier = Supplier(company_id=company.id, name="Northline Steel")
    db_session.add(supplier)
    db_session.flush()

    product = Product(company_id=company.id, supplier_id=supplier.id, name="Sensor Module", sku="PCB-011", unit_cost=unit_cost)
    db_session.add(product)
    db_session.commit()

    return supplier, product


def _orchestrator(db_session, event_bus):
    return AIOrchestrator(db_session, build_capability_registry(), DeterministicLLMClient(), event_bus)


def test_procurement_question_routes_to_procurement_agent(db_session, event_bus):
    supplier, product = _make_supplier_and_product(db_session)

    result = _orchestrator(db_session, event_bus).ask("What is our supplier for the Sensor Module?")

    assert result.agent == "procurement"
    assert "read_product" in result.capabilities_used
    assert "read_supplier" in result.capabilities_used
    assert "read_transactions" in result.capabilities_used
    assert "analyze_margin" not in result.capabilities_used
    assert result.requires_human_validation is False
    assert result.action_result is None


def test_margin_question_is_cross_domain(db_session, event_bus):
    """A margin question genuinely needs Finance + Procurement (+ Sales, if a
    customer is mentioned): this is the architectural point of step 12 -- no
    single agent should gate access to the capabilities needed to answer it."""

    supplier, product = _make_supplier_and_product(db_session)
    db_session.add(
        Transaction(
            company_id=supplier.company_id,
            supplier_id=supplier.id,
            product_id=product.id,
            type=TransactionType.PURCHASE_ORDER,
            status=TransactionStatus.CONFIRMED,
            amount=610.0,
            currency="EUR",
            occurred_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    result = _orchestrator(db_session, event_bus).ask("What is our margin on the Sensor Module?")

    assert "finance" in result.agent
    assert "procurement" in result.agent
    assert "analyze_margin" in result.capabilities_used
    assert "read_transactions" in result.capabilities_used
    # Cross-domain: the procurement context (who the supplier is) comes along
    # automatically, without the question ever mentioning "supplier".
    assert "read_supplier" in result.capabilities_used
    assert "read_product" in result.capabilities_used


def test_sales_question_routes_to_sales_agent(db_session, event_bus):
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


def test_priorities_question_lists_open_risks_and_opportunities(db_session, event_bus):
    result = _orchestrator(db_session, event_bus).ask("What deserves my attention today?")

    assert result.agent == "priorities"
    # On an empty business, the Snapshot has no material areas, so nothing to
    # drill into -- only the two summary capabilities run.
    assert result.capabilities_used == ["list_priorities", "get_business_state_snapshot"]
    assert "priorities" in result.context["list_priorities"]
    assert result.context["get_business_state_snapshot"]["material_areas"] == []


def test_context_reflects_real_database_values(db_session, event_bus):
    supplier, product = _make_supplier_and_product(db_session, unit_cost=61.0)

    result = _orchestrator(db_session, event_bus).ask("What is the current supplier cost for the Sensor Module?")

    assert result.context["read_product"]["unit_cost"] == 61.0
    assert result.context["read_supplier"]["name"] == "Northline Steel"
    # Step 27: without a real LLM configured, `answer` is a clean French
    # summary built from this same real context -- never a raw JSON/prompt
    # dump -- so it reflects the real product/supplier, in business language.
    assert "Sensor Module" in result.answer
    assert "Northline Steel" in result.answer
    assert "Context:" not in result.answer
    assert "{" not in result.answer


def test_french_question_routes_the_same_as_its_english_equivalent(db_session, event_bus):
    """Step 26: the frontend is entirely in French, so a real user's question
    arrives in French -- the keyword routing must actually handle that, not
    just the English phrasing the rest of this file exercises."""

    supplier, product = _make_supplier_and_product(db_session)

    result = _orchestrator(db_session, event_bus).ask("Quel est notre fournisseur pour le Sensor Module ?")

    assert result.agent == "procurement"
    assert "read_product" in result.capabilities_used
    assert "read_supplier" in result.capabilities_used


def test_unroutable_question_raises_a_clean_error(db_session, event_bus):
    with pytest.raises(OrchestratorError):
        _orchestrator(db_session, event_bus).ask("What time is it?")


def test_unresolvable_entity_raises_a_clean_error(db_session, event_bus):
    _make_supplier_and_product(db_session)

    with pytest.raises(OrchestratorError):
        _orchestrator(db_session, event_bus).ask("What is our supplier situation?")


def test_empty_question_raises_a_clean_error(db_session, event_bus):
    with pytest.raises(OrchestratorError):
        _orchestrator(db_session, event_bus).ask("   ")
