"""app.core.entity_context.get_entity_context: the Data Core's own small,
transverse read for "what's directly around this entity?" -- plain
structural reads, no Baseline/Significance/Interpretation, no LLM."""

from datetime import datetime, timedelta, timezone

from app.core.entities import (
    Communication,
    CommunicationDirection,
    Company,
    Contact,
    Customer,
    Document,
    Opportunity,
    OpportunityStatus,
    Product,
    RelatedEntityType,
    Risk,
    RiskSeverity,
    RiskStatus,
    Supplier,
    Task,
    TaskStatus,
    Transaction,
    TransactionStatus,
    TransactionType,
)
from app.core.entity_context import get_entity_context


def _seed_supplier_with_product_and_transaction(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()
    supplier = Supplier(company_id=company.id, name="Northline")
    db_session.add(supplier)
    db_session.flush()
    product = Product(company_id=company.id, supplier_id=supplier.id, name="Frame", sku="F-1")
    db_session.add(product)
    db_session.flush()
    db_session.add(
        Transaction(
            company_id=company.id, supplier_id=supplier.id, product_id=product.id,
            type=TransactionType.PURCHASE_ORDER, status=TransactionStatus.CONFIRMED,
            amount=500.0, currency="EUR", occurred_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()
    return company, supplier, product


def test_entity_context_for_a_supplier_includes_products_and_transactions(db_session):
    company, supplier, product = _seed_supplier_with_product_and_transaction(db_session)

    context = get_entity_context(db_session, RelatedEntityType.SUPPLIER, supplier.id)

    assert context["found"] is True
    assert context["name"] == "Northline"
    assert [p["id"] for p in context["products"]] == [product.id]
    assert len(context["transactions"]) == 1
    assert context["transactions"][0]["amount"] == 500.0


def test_entity_context_for_a_product_includes_its_supplier_and_transactions(db_session):
    company, supplier, product = _seed_supplier_with_product_and_transaction(db_session)

    context = get_entity_context(db_session, RelatedEntityType.PRODUCT, product.id)

    assert context["found"] is True
    assert context["supplier"]["id"] == supplier.id
    assert len(context["transactions"]) == 1
    assert context["transactions"][0]["product_id"] == product.id


def test_entity_context_for_a_customer_includes_its_transactions(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()
    customer = Customer(company_id=company.id, name="Buyer Co")
    db_session.add(customer)
    db_session.flush()
    db_session.add(
        Transaction(
            company_id=company.id, customer_id=customer.id,
            type=TransactionType.SALES_ORDER, status=TransactionStatus.CONFIRMED,
            amount=750.0, currency="EUR", occurred_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    context = get_entity_context(db_session, RelatedEntityType.CUSTOMER, customer.id)

    assert context["found"] is True
    assert context["name"] == "Buyer Co"
    assert len(context["transactions"]) == 1
    assert context["transactions"][0]["amount"] == 750.0


def test_entity_context_includes_open_risks_opportunities_tasks_documents_and_communications(db_session):
    company, supplier, product = _seed_supplier_with_product_and_transaction(db_session)

    db_session.add(
        Risk(
            company_id=company.id, title="Supplier cost increase", severity=RiskSeverity.HIGH,
            status=RiskStatus.OPEN, related_entity_type=RelatedEntityType.SUPPLIER, related_entity_id=supplier.id,
        )
    )
    db_session.add(
        Opportunity(
            company_id=company.id, title="Bulk discount available", status=OpportunityStatus.OPEN,
            related_entity_type=RelatedEntityType.SUPPLIER, related_entity_id=supplier.id,
        )
    )
    db_session.add(
        Task(
            company_id=company.id, title="Review supplier", status=TaskStatus.PENDING_VALIDATION,
            related_entity_type=RelatedEntityType.SUPPLIER, related_entity_id=supplier.id,
        )
    )
    db_session.add(
        Document(
            company_id=company.id, title="Contract.pdf", document_type="contract",
            related_entity_type=RelatedEntityType.SUPPLIER, related_entity_id=supplier.id,
        )
    )
    db_session.add(
        Communication(
            company_id=company.id, channel="email", direction=CommunicationDirection.OUTBOUND,
            subject="Renewal", occurred_at=datetime.now(timezone.utc),
            related_entity_type=RelatedEntityType.SUPPLIER, related_entity_id=supplier.id,
        )
    )
    db_session.commit()

    context = get_entity_context(db_session, RelatedEntityType.SUPPLIER, supplier.id)

    assert len(context["open_risks"]) == 1
    assert len(context["open_opportunities"]) == 1
    assert len(context["tasks"]) == 1
    assert len(context["documents"]) == 1
    assert len(context["communications"]) == 1


def test_entity_context_includes_linked_contacts(db_session):
    company, supplier, product = _seed_supplier_with_product_and_transaction(db_session)

    db_session.add(
        Contact(
            company_id=company.id, name="Ana Silva", role="Responsable commerciale",
            email="ana@example.com", phone="+351 21 000 0000",
            related_entity_type=RelatedEntityType.SUPPLIER, related_entity_id=supplier.id,
        )
    )
    db_session.commit()

    context = get_entity_context(db_session, RelatedEntityType.SUPPLIER, supplier.id)

    assert len(context["contacts"]) == 1
    assert context["contacts"][0]["name"] == "Ana Silva"
    assert context["contacts"][0]["email"] == "ana@example.com"


def test_entity_context_excludes_a_resolved_risk_or_dismissed_opportunity(db_session):
    company, supplier, product = _seed_supplier_with_product_and_transaction(db_session)

    db_session.add(
        Risk(
            company_id=company.id, title="Old risk", severity=RiskSeverity.LOW,
            status=RiskStatus.RESOLVED, related_entity_type=RelatedEntityType.SUPPLIER, related_entity_id=supplier.id,
        )
    )
    db_session.commit()

    context = get_entity_context(db_session, RelatedEntityType.SUPPLIER, supplier.id)
    assert context["open_risks"] == []


def test_entity_context_includes_related_business_events(db_session, session_factory):
    from app.core.events.bus import InProcessEventBus
    from app.core.events.log_handler import make_event_log_handler
    from app.observation import build_observable_registry
    from app.observation.engine import run_observation_sweep
    from app.business_context.service import BusinessContextService

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

    run_observation_sweep(db_session, bus, build_observable_registry(), company.id)

    context = get_entity_context(db_session, RelatedEntityType.PRODUCT, product.id)
    event_types = {e["event_type"] for e in context["related_events"]}
    assert "ObservationDetected" in event_types


def test_entity_context_for_an_unknown_id_is_not_found_not_an_error(db_session):
    import uuid

    context = get_entity_context(db_session, RelatedEntityType.SUPPLIER, uuid.uuid4())
    assert context["found"] is False


def test_entity_context_for_an_unsupported_entity_type_is_not_found(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.commit()

    context = get_entity_context(db_session, RelatedEntityType.COMPANY, company.id)
    assert context["found"] is False
