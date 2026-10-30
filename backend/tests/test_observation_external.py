"""Step 22: the two external-data Observables (app.observation, reading
Communication rows the Connector Layer ingests) -- computation only, via the
exact same Observable/Baseline/Significance machinery as the three original
metrics. No connector, no Interpretation/Decision here."""

from datetime import datetime, timedelta, timezone

from app.business_context.service import BusinessContextService
from app.core.analytics import compute_unanswered_message_age
from app.core.baseline import customer_unanswered_message_baseline, supplier_unanswered_message_baseline
from app.core.entities import (
    Communication,
    CommunicationDirection,
    Company,
    Customer,
    RelatedEntityType,
    Supplier,
)
from app.observation import build_observable_registry
from app.observation.engine import compute_observation


def _company(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()
    return company


def test_compute_unanswered_message_age_with_no_communications_is_none(db_session):
    company = _company(db_session)
    supplier = Supplier(company_id=company.id, name="Northline")
    db_session.add(supplier)
    db_session.commit()

    result = compute_unanswered_message_age(db_session, RelatedEntityType.SUPPLIER, supplier.id)
    assert result.sample_size == 0
    assert result.age_days is None


def test_compute_unanswered_message_age_finds_the_oldest_unanswered_inbound_message(db_session):
    company = _company(db_session)
    supplier = Supplier(company_id=company.id, name="Northline")
    db_session.add(supplier)
    db_session.flush()

    now = datetime.now(timezone.utc)
    db_session.add(
        Communication(
            company_id=company.id, channel="email", direction=CommunicationDirection.INBOUND,
            subject="Older message", occurred_at=now - timedelta(days=9),
            related_entity_type=RelatedEntityType.SUPPLIER, related_entity_id=supplier.id,
        )
    )
    db_session.add(
        Communication(
            company_id=company.id, channel="email", direction=CommunicationDirection.INBOUND,
            subject="Newer message", occurred_at=now - timedelta(days=1),
            related_entity_type=RelatedEntityType.SUPPLIER, related_entity_id=supplier.id,
        )
    )
    db_session.commit()

    result = compute_unanswered_message_age(db_session, RelatedEntityType.SUPPLIER, supplier.id, now=now)
    assert result.sample_size == 2
    assert result.subject == "Older message"
    assert 8.9 < result.age_days < 9.1


def test_an_outbound_reply_after_the_message_counts_as_answered(db_session):
    company = _company(db_session)
    supplier = Supplier(company_id=company.id, name="Northline")
    db_session.add(supplier)
    db_session.flush()

    now = datetime.now(timezone.utc)
    db_session.add(
        Communication(
            company_id=company.id, channel="email", direction=CommunicationDirection.INBOUND,
            subject="Please respond", occurred_at=now - timedelta(days=9),
            related_entity_type=RelatedEntityType.SUPPLIER, related_entity_id=supplier.id,
        )
    )
    db_session.add(
        Communication(
            company_id=company.id, channel="email", direction=CommunicationDirection.OUTBOUND,
            subject="Re: Please respond", occurred_at=now - timedelta(days=8),
            related_entity_type=RelatedEntityType.SUPPLIER, related_entity_id=supplier.id,
        )
    )
    db_session.commit()

    result = compute_unanswered_message_age(db_session, RelatedEntityType.SUPPLIER, supplier.id, now=now)
    assert result.age_days is None  # answered -- no longer unanswered


def test_a_future_scheduled_outbound_event_does_not_count_as_already_answering(db_session):
    """A calendar event scheduled for later this week hasn't happened yet --
    it cannot retroactively count as "the message was answered" just
    because its occurred_at timestamp is later than the inbound message's."""

    company = _company(db_session)
    supplier = Supplier(company_id=company.id, name="Northline")
    db_session.add(supplier)
    db_session.flush()

    now = datetime.now(timezone.utc)
    db_session.add(
        Communication(
            company_id=company.id, channel="email", direction=CommunicationDirection.INBOUND,
            subject="Please respond", occurred_at=now - timedelta(days=9),
            related_entity_type=RelatedEntityType.SUPPLIER, related_entity_id=supplier.id,
        )
    )
    db_session.add(
        Communication(
            company_id=company.id, channel="calendar", direction=CommunicationDirection.OUTBOUND,
            subject="Upcoming call", occurred_at=now + timedelta(days=2),  # in the future
            related_entity_type=RelatedEntityType.SUPPLIER, related_entity_id=supplier.id,
        )
    )
    db_session.commit()

    result = compute_unanswered_message_age(db_session, RelatedEntityType.SUPPLIER, supplier.id, now=now)
    assert result.age_days is not None
    assert 8.9 < result.age_days < 9.1


def test_baseline_wrappers_use_a_declared_expectation_when_present(db_session):
    company = _company(db_session)
    context = BusinessContextService(db_session).update(company.id, declared_baselines={"unanswered_message_age_days": 3})
    supplier = Supplier(company_id=company.id, name="Northline")
    db_session.add(supplier)
    db_session.flush()

    now = datetime.now(timezone.utc)
    db_session.add(
        Communication(
            company_id=company.id, channel="email", direction=CommunicationDirection.INBOUND,
            subject="Please respond", occurred_at=now - timedelta(days=9),
            related_entity_type=RelatedEntityType.SUPPLIER, related_entity_id=supplier.id,
        )
    )
    db_session.commit()

    baseline, current_value = supplier_unanswered_message_baseline(db_session, supplier.id, context)
    assert baseline.source == "declared"
    assert baseline.confidence == "high"
    assert baseline.reference_value == 3
    assert current_value > 8


def test_customer_unanswered_message_baseline_falls_back_to_generic_benchmark(db_session):
    company = _company(db_session)
    customer = Customer(company_id=company.id, name="Buyer Co")
    db_session.add(customer)
    db_session.flush()

    now = datetime.now(timezone.utc)
    db_session.add(
        Communication(
            company_id=company.id, channel="website", direction=CommunicationDirection.INBOUND,
            subject="Inquiry", occurred_at=now - timedelta(days=5),
            related_entity_type=RelatedEntityType.CUSTOMER, related_entity_id=customer.id,
        )
    )
    db_session.commit()

    baseline, current_value = customer_unanswered_message_baseline(db_session, customer.id, None)
    assert baseline.source == "generic_fallback"
    assert baseline.confidence == "low"
    assert current_value > 4


# --- Registered as real Observables, computed via the shared engine function


def test_supplier_unanswered_observable_is_registered_and_computes_via_the_engine(db_session):
    company = _company(db_session)
    context = BusinessContextService(db_session).get_or_create(company.id)
    supplier = Supplier(company_id=company.id, name="Northline")
    db_session.add(supplier)
    db_session.flush()

    now = datetime.now(timezone.utc)
    db_session.add(
        Communication(
            company_id=company.id, channel="email", direction=CommunicationDirection.INBOUND,
            subject="Pricing renegotiation", body="We need to revisit pricing.",
            occurred_at=now - timedelta(days=9),
            related_entity_type=RelatedEntityType.SUPPLIER, related_entity_id=supplier.id,
        )
    )
    db_session.commit()

    registry = build_observable_registry()
    observable = registry.get("supplier_unanswered_message_age_days")
    observation = compute_observation(db_session, observable, supplier.id, context)

    assert observation.is_anomalous is True
    assert observation.extra_context["message_subject"] == "Pricing renegotiation"
    assert "revisit pricing" in observation.extra_context["message_excerpt"]


def test_customer_unanswered_observable_is_registered():
    registry = build_observable_registry()
    observable = registry.get("customer_unanswered_message_age_days")
    assert observable.domain == "sales"
    assert observable.entity_type == RelatedEntityType.CUSTOMER
