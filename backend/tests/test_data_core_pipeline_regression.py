"""Step 20: proof that reinforcing the Data Core (the Product<->Transaction
relationship, app.core.entity_context) changed nothing about how every
higher layer behaves -- one real, end-to-end run of the full chain:

    Data Core -> Observation -> Interpretation -> Decision -> AI Orchestrator
    (cross-domain) -> Home / Command Center

against the same kind of scenario steps 15-19's own test suites already
cover, run again here specifically to guard against a Data Core change
silently breaking a downstream layer."""

from datetime import datetime, timedelta, timezone

from app.ai.capabilities import build_capability_registry
from app.ai.llm import DeterministicLLMClient
from app.ai.orchestrator import AIOrchestrator
from app.business_context.service import BusinessContextService
from app.core.entities import Company, Customer, Product, Supplier, Transaction, TransactionStatus, TransactionType
from app.core.events.bus import InProcessEventBus
from app.core.events.log_handler import make_event_log_handler
from app.decision.engine import run_decision_sweep
from app.home.service import HomeService
from app.interpretation.engine import run_interpretation_sweep
from app.observation import build_observable_registry
from app.observation.engine import run_observation_sweep


def test_full_chain_still_works_after_the_data_core_relationship_fix(db_session, session_factory):
    bus = InProcessEventBus()
    bus.subscribe("*", make_event_log_handler(session_factory))

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

    # Product's new `transactions` relationship must not change what the
    # rest of the system already computes from a direct filtered query.
    assert len(product.transactions) == 8

    registry = build_capability_registry()
    llm = DeterministicLLMClient()

    observation_result = run_observation_sweep(db_session, bus, build_observable_registry(), company.id)
    assert observation_result["business_events_published"] == 1

    interpretation_result = run_interpretation_sweep(db_session, bus, registry, llm, company.id)
    assert interpretation_result["by_type"]["risk"] == 1

    decision_result = run_decision_sweep(db_session, bus, registry, llm, company.id)
    assert decision_result["by_type"]["risk"] == 1
    assert decision_result["actions_proposed"] == 1

    orchestrator = AIOrchestrator(db_session, registry, llm, bus)
    result = orchestrator.ask("Why is our margin declining?")
    assert "finance" in result.agent
    assert "analyze_margin" in result.capabilities_used

    view = HomeService(db_session).get_command_center(company.id)
    assert len(view["priorities"]) == 1
    assert view["priorities"][0]["kind"] == "decision"
    assert len(view["decisions"]) == 1
    assert view["tasks"]["pending_validation_tasks"] == 1
