import uuid
from datetime import datetime, timedelta, timezone

from app.core.entities import (
    Communication,
    CommunicationDirection,
    Company,
    Customer,
    EventLogEntry,
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
from app.home.service import HomeService


def _make_supplier_and_product(db_session, unit_cost=100.0):
    company = Company(name="Test Co")
    db_session.add(company)
    db_session.flush()

    supplier = Supplier(company_id=company.id, name="Test Supplier")
    db_session.add(supplier)
    db_session.flush()

    product = Product(company_id=company.id, supplier_id=supplier.id, name="Widget", sku="W-1", unit_cost=unit_cost)
    db_session.add(product)
    db_session.commit()

    return supplier, product


def test_home_is_empty_with_no_data(db_session):
    # No Company at all yet -- the explicit "insufficient context" state for
    # priorities (which need a company_id for the Snapshot), never a guess.
    view = HomeService(db_session).get_command_center(company_id=None)

    assert view["overview"] == {
        "supplier_count": 0,
        "product_count": 0,
        "customer_count": 0,
        "transaction_count": 0,
    }
    assert view["priorities"] == []
    assert view["risks"]["total_risks"] == 0
    assert view["risks"]["recent_risks"] == []
    assert view["decisions"] == []
    assert view["tasks"]["total_tasks"] == 0
    assert view["tasks"]["recent_tasks"] == []
    assert view["recent_events"] == []


def test_home_overview_matches_db_counts(db_session):
    supplier, product = _make_supplier_and_product(db_session)
    db_session.add(
        Transaction(
            company_id=supplier.company_id,
            supplier_id=supplier.id,
            product_id=product.id,
            type=TransactionType.PURCHASE_ORDER,
            status=TransactionStatus.CONFIRMED,
            amount=100.0,
            currency="EUR",
            occurred_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    overview = HomeService(db_session).get_overview()

    assert overview == {"supplier_count": 1, "product_count": 1, "customer_count": 0, "transaction_count": 1}


def test_home_reflects_an_existing_risk(db_session):
    supplier, _product = _make_supplier_and_product(db_session)
    risk = Risk(
        company_id=supplier.company_id,
        title="Supplier cost increase of 20% on product Widget",
        description="Unit cost rose from 100.0 to 120.0 (20.0%).",
        severity=RiskSeverity.HIGH,
        status=RiskStatus.OPEN,
        related_entity_type=RelatedEntityType.SUPPLIER,
        related_entity_id=supplier.id,
        source_event_id=uuid.uuid4(),
    )
    db_session.add(risk)
    db_session.commit()

    risks = HomeService(db_session).get_risks_summary()

    assert risks["total_risks"] == 1
    assert risks["high_risks"] == 1
    assert [r.id for r in risks["recent_risks"]] == [risk.id]


def test_home_reflects_a_pending_validation_task(db_session):
    supplier, _product = _make_supplier_and_product(db_session)
    task = Task(
        company_id=supplier.company_id,
        title="Review supplier cost increase",
        description="Supplier cost increase of 20% on product Widget.",
        status=TaskStatus.PENDING_VALIDATION,
        related_entity_type=RelatedEntityType.SUPPLIER,
        related_entity_id=supplier.id,
        source_event_id=uuid.uuid4(),
    )
    db_session.add(task)
    db_session.commit()

    tasks = HomeService(db_session).get_tasks_summary()

    assert tasks["total_tasks"] == 1
    assert tasks["pending_validation_tasks"] == 1
    assert [t.id for t in tasks["recent_tasks"]] == [task.id]


def test_os_activity_translates_observation_detected_into_french_without_raw_payload(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.commit()

    db_session.add(
        EventLogEntry(
            event_id=uuid.uuid4(),
            event_type="ObservationDetected",
            source="observation_engine",
            correlation_id=uuid.uuid4(),
            occurred_at=datetime.now(timezone.utc),
            payload={"domain": "procurement", "observable": "delivery_delay_days", "entity_name": "Iberia Logistics Parts"},
        )
    )
    db_session.commit()

    activity = HomeService(db_session).get_os_activity()

    assert len(activity) == 1
    assert activity[0]["domain"] == "procurement"
    assert activity[0]["label"] == "Analyse effectuée"
    assert "Iberia Logistics Parts" in activity[0]["detail"]
    assert "delivery_delay_days" not in activity[0]["detail"]  # translated, not the raw observable key


def test_os_activity_skips_event_types_it_does_not_narrate(db_session):
    db_session.add(
        EventLogEntry(
            event_id=uuid.uuid4(),
            event_type="RiskCreated",  # the older per-metric pipeline's event -- deliberately not narrated here
            source="risk_service",
            correlation_id=uuid.uuid4(),
            occurred_at=datetime.now(timezone.utc),
            payload={"risk_id": str(uuid.uuid4())},
        )
    )
    db_session.commit()

    assert HomeService(db_session).get_os_activity() == []


def test_os_activity_filters_by_domain(db_session):
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            EventLogEntry(
                event_id=uuid.uuid4(), event_type="ObservationDetected", source="observation_engine",
                correlation_id=uuid.uuid4(), occurred_at=now,
                payload={"domain": "finance", "observable": "margin_pct", "entity_name": "Steel Frame Assembly"},
            ),
            EventLogEntry(
                event_id=uuid.uuid4(), event_type="ObservationDetected", source="observation_engine",
                correlation_id=uuid.uuid4(), occurred_at=now,
                payload={"domain": "sales", "observable": "customer_revenue_variation_pct", "entity_name": "Metroline Corp"},
            ),
        ]
    )
    db_session.commit()

    assert len(HomeService(db_session).get_os_activity(domain="finance")) == 1
    assert len(HomeService(db_session).get_os_activity()) == 2


def test_company_narrative_returns_real_communications_with_entity_name_resolved(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()
    customer = Customer(company_id=company.id, name="Vantix Group")
    db_session.add(customer)
    db_session.flush()
    db_session.add(
        Communication(
            company_id=company.id, channel="email", channel_detail="contract_signed",
            direction=CommunicationDirection.INBOUND, subject="Contrat signé", body="...",
            related_entity_type=RelatedEntityType.CUSTOMER, related_entity_id=customer.id,
            occurred_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
    )
    db_session.commit()

    narrative = HomeService(db_session).get_company_narrative(company.id)

    assert len(narrative) == 1
    assert narrative[0]["subject"] == "Contrat signé"
    assert narrative[0]["related_entity_name"] == "Vantix Group"
    assert narrative[0]["channel_detail"] == "contract_signed"


def test_company_narrative_excludes_calendar_and_website_channels(db_session):
    """A future-dated calendar event is not "what happened" (Step 27) --
    without this, mock-calendar meetings scheduled days ahead would crowd
    out the real business narrative in the most-recent-first ordering."""

    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()
    db_session.add_all(
        [
            Communication(
                company_id=company.id, channel="calendar", direction=CommunicationDirection.OUTBOUND,
                subject="Team sync", occurred_at=datetime.now(timezone.utc) + timedelta(days=3),
            ),
            Communication(
                company_id=company.id, channel="website", direction=CommunicationDirection.INBOUND,
                subject="Quote request", occurred_at=datetime.now(timezone.utc),
            ),
            Communication(
                company_id=company.id, channel="internal", channel_detail="employee_idea",
                direction=CommunicationDirection.INBOUND, subject="Idée", occurred_at=datetime.now(timezone.utc) - timedelta(hours=1),
            ),
        ]
    )
    db_session.commit()

    narrative = HomeService(db_session).get_company_narrative(company.id)

    assert len(narrative) == 1
    assert narrative[0]["subject"] == "Idée"
