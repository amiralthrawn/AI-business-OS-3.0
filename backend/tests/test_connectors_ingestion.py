"""Ingestion (app.connectors.ingestion): fetch -> normalize -> ingest ->
Data Core, for each of the three Mock Providers. Covers entity resolution
(a known Supplier/Customer vs. an unresolved external contact), provenance,
idempotence and no-duplicate-Contact reuse."""

from app.connectors.calendar.mock import MockCalendarProvider
from app.connectors.email.mock import MockEmailProvider
from app.connectors.ingestion import ingest_calendar, ingest_email, ingest_website, sync_connector
from app.connectors.website.mock import MockWebsiteProvider
from app.core.entities import Communication, Company, Contact, Customer, Document, RelatedEntityType, Supplier


def _company_with_known_entities(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()
    db_session.add(Supplier(company_id=company.id, name="Northline Steel"))
    db_session.add(Customer(company_id=company.id, name="Metroline Corp"))
    db_session.commit()
    return company


# --- Email ingestion ----------------------------------------------------------


def test_ingest_email_creates_communications_with_provenance(db_session):
    company = _company_with_known_entities(db_session)

    result = ingest_email(db_session, MockEmailProvider(), company.id)

    assert result.connector == "email"
    assert result.fetched >= 7
    assert result.created == result.fetched
    assert result.skipped == 0

    comm = db_session.query(Communication).filter_by(external_id="email_001").one()
    assert comm.source == "mock_email"
    assert comm.channel == "email"
    assert comm.subject == "Steel pricing renegotiation"


def test_ingest_email_resolves_a_known_supplier_by_domain(db_session):
    company = _company_with_known_entities(db_session)
    supplier = db_session.query(Supplier).filter_by(name="Northline Steel").one()

    ingest_email(db_session, MockEmailProvider(), company.id)

    comm = db_session.query(Communication).filter_by(external_id="email_001").one()
    assert comm.related_entity_type == RelatedEntityType.SUPPLIER
    assert comm.related_entity_id == supplier.id


def test_ingest_email_leaves_an_unknown_sender_as_an_unresolved_contact(db_session):
    company = _company_with_known_entities(db_session)

    ingest_email(db_session, MockEmailProvider(), company.id)

    comm = db_session.query(Communication).filter_by(external_id="email_003").one()  # Thornfield prospect
    assert comm.related_entity_type is None
    assert comm.related_entity_id is None

    contact = db_session.query(Contact).filter_by(email="sales@thornfieldindustries.example").one()
    assert contact.related_entity_type is None


def test_ingest_email_reuses_the_same_contact_across_two_messages(db_session):
    company = _company_with_known_entities(db_session)

    ingest_email(db_session, MockEmailProvider(), company.id)

    contacts = db_session.query(Contact).filter_by(email="procurement@northlinesteel.com").all()
    assert len(contacts) == 1  # email_001 and email_007 share a sender -- one Contact, not two


def test_ingest_email_creates_a_document_for_the_invoice_attachment(db_session):
    company = _company_with_known_entities(db_session)

    ingest_email(db_session, MockEmailProvider(), company.id)

    document = db_session.query(Document).filter_by(source="mock_email").one()
    assert document.title == "invoice_INV-2050.pdf"
    assert document.document_type == "email_attachment"


def test_ingest_email_is_idempotent(db_session):
    company = _company_with_known_entities(db_session)

    first = ingest_email(db_session, MockEmailProvider(), company.id)
    second = ingest_email(db_session, MockEmailProvider(), company.id)

    assert second.created == 0
    assert second.skipped == first.fetched
    assert db_session.query(Communication).filter_by(source="mock_email").count() == first.fetched


# --- Calendar ingestion --------------------------------------------------------


def test_ingest_calendar_creates_communications_and_resolves_attendees(db_session):
    company = _company_with_known_entities(db_session)
    supplier = db_session.query(Supplier).filter_by(name="Northline Steel").one()

    result = ingest_calendar(db_session, MockCalendarProvider(), company.id)

    assert result.connector == "calendar"
    assert result.created > 0

    comm = db_session.query(Communication).filter_by(external_id="calendar_003").one()
    assert comm.source == "mock_calendar"
    assert comm.channel == "calendar"
    assert comm.related_entity_type == RelatedEntityType.SUPPLIER
    assert comm.related_entity_id == supplier.id


def test_ingest_calendar_is_idempotent(db_session):
    company = _company_with_known_entities(db_session)

    first = ingest_calendar(db_session, MockCalendarProvider(), company.id)
    second = ingest_calendar(db_session, MockCalendarProvider(), company.id)

    assert second.created == 0
    assert db_session.query(Communication).filter_by(source="mock_calendar").count() == first.created


# --- Website ingestion ---------------------------------------------------------


def test_ingest_website_resolves_an_existing_customer_by_company_name(db_session):
    company = _company_with_known_entities(db_session)
    customer = db_session.query(Customer).filter_by(name="Metroline Corp").one()

    ingest_website(db_session, MockWebsiteProvider(), company.id)

    comm = db_session.query(Communication).filter_by(external_id="web_004").one()
    assert comm.related_entity_type == RelatedEntityType.CUSTOMER
    assert comm.related_entity_id == customer.id


def test_ingest_website_leaves_an_unknown_prospect_unresolved(db_session):
    company = _company_with_known_entities(db_session)

    ingest_website(db_session, MockWebsiteProvider(), company.id)

    comm = db_session.query(Communication).filter_by(external_id="web_007").one()  # spam, no real company
    assert comm.related_entity_type is None


def test_ingest_website_preserves_the_inquirys_own_source(db_session):
    """Step 23B fix: `WebsiteInquiry.source` (e.g. "contact_form" vs
    "quote_form") was previously computed by the provider and silently
    dropped during ingestion -- a real gap the step 23 audit found. It must
    now land on `Communication.channel_detail`."""

    company = _company_with_known_entities(db_session)

    ingest_website(db_session, MockWebsiteProvider(), company.id)

    comm = db_session.query(Communication).filter_by(external_id="web_002").one()  # a "quote_form" inquiry
    assert comm.channel_detail == "quote_form"


def test_ingest_website_marks_inquiries_processed_on_the_provider(db_session):
    company = _company_with_known_entities(db_session)
    provider = MockWebsiteProvider()

    ingest_website(db_session, provider, company.id)

    assert provider.get_inquiry("web_001").status == "processed"


def test_ingest_website_is_idempotent(db_session):
    company = _company_with_known_entities(db_session)
    provider = MockWebsiteProvider()

    first = ingest_website(db_session, provider, company.id)
    second = ingest_website(db_session, provider, company.id)

    assert second.created == 0
    assert db_session.query(Communication).filter_by(source="mock_website").count() == first.created


# --- Dispatcher -----------------------------------------------------------------


def test_sync_connector_dispatches_to_the_right_ingestion_function(db_session):
    company = _company_with_known_entities(db_session)

    result = sync_connector(db_session, "email", MockEmailProvider(), company.id)
    assert result.connector == "email"


def test_sync_connector_rejects_an_unknown_type(db_session):
    company = _company_with_known_entities(db_session)
    import pytest

    with pytest.raises(KeyError):
        sync_connector(db_session, "sms", object(), company.id)
