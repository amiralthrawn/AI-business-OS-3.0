"""Mock Providers (app.connectors.email/calendar/website.mock) and the
normalized external objects they return (app.connectors.models). No Data
Core, no business logic here -- just the provider interfaces themselves."""

from datetime import datetime, timedelta, timezone

from app.connectors.calendar.mock import MockCalendarProvider
from app.connectors.email.mock import MockEmailProvider
from app.connectors.models import ExternalCalendarEvent, ExternalEmail, WebsiteInquiry
from app.connectors.website.mock import MockWebsiteProvider


# --- Normalization: the shared shape every provider must produce -----------


def test_external_email_has_the_expected_normalized_fields():
    email = ExternalEmail(
        external_id="e1", thread_id="t1", sender="a@example.com", recipients=["b@example.com"],
        subject="Hi", body="Body", timestamp=datetime.now(timezone.utc),
    )
    assert email.direction == "inbound"
    assert email.attachments == []
    assert email.status == "unread"


def test_external_calendar_event_and_website_inquiry_have_the_expected_fields():
    event = ExternalCalendarEvent(
        external_id="c1", title="Call", start=datetime.now(timezone.utc), end=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    assert event.attendees == []
    assert event.status == "confirmed"

    inquiry = WebsiteInquiry(
        external_id="w1", name="A", email="a@example.com", subject="S", message="M", timestamp=datetime.now(timezone.utc),
    )
    assert inquiry.status == "new"
    assert inquiry.source == "contact_form"


# --- MockEmailProvider -------------------------------------------------------


def test_mock_email_provider_lists_a_realistic_dataset():
    provider = MockEmailProvider()
    messages = provider.list_messages()

    assert len(messages) >= 7
    senders = {m.sender for m in messages}
    assert "procurement@northlinesteel.com" in senders  # supplier renegotiation
    assert "ops@brightworks.co.uk" in senders  # customer delivery complaint
    assert any(m.attachments for m in messages)  # the invoice
    assert any(m.direction == "outbound" for m in messages)


def test_mock_email_provider_get_and_search():
    provider = MockEmailProvider()
    message = provider.get_message("email_001")
    assert message is not None
    assert message.subject == "Steel pricing renegotiation"

    assert provider.get_message("does_not_exist") is None
    assert len(provider.search_messages("renegotiation")) >= 1


def test_mock_email_provider_send_message_only_affects_its_own_mailbox():
    provider = MockEmailProvider()
    before = len(provider.list_messages())

    sent = provider.send_message(recipients=["client@example.com"], subject="Follow up", body="...")

    assert sent.direction == "outbound"
    assert len(provider.list_messages()) == before + 1


# --- MockCalendarProvider ----------------------------------------------------


def test_mock_calendar_provider_lists_events_in_range_including_a_real_conflict():
    provider = MockCalendarProvider()
    now = datetime.now(timezone.utc)
    events = provider.list_events(now - timedelta(days=5), now + timedelta(days=10))

    assert len(events) >= 5
    # calendar_003 and calendar_004 deliberately overlap.
    by_id = {e.external_id: e for e in events}
    a, b = by_id["calendar_003"], by_id["calendar_004"]
    assert a.start < b.end and b.start < a.end


def test_mock_calendar_provider_availability_skips_confirmed_events():
    provider = MockCalendarProvider()
    now = datetime.now(timezone.utc)
    window_start = now + timedelta(days=2)
    window_end = now + timedelta(days=2, hours=4)

    slots = provider.get_availability(window_start, window_end)

    for slot_start, slot_end in slots:
        for event in provider.list_events(window_start, window_end):
            if event.status == "cancelled":
                continue
            assert not (event.start < slot_end and slot_start < event.end)


def test_mock_calendar_provider_create_update_cancel():
    provider = MockCalendarProvider()
    now = datetime.now(timezone.utc)

    created = provider.create_event(title="New call", start=now, end=now + timedelta(hours=1), attendees=["x@example.com"])
    assert provider.get_event(created.external_id) is not None

    updated = provider.update_event(created.external_id, title="Renamed call")
    assert updated.title == "Renamed call"

    cancelled = provider.cancel_event(created.external_id)
    assert cancelled.status == "cancelled"


# --- MockWebsiteProvider ------------------------------------------------------


def test_mock_website_provider_lists_a_realistic_dataset():
    provider = MockWebsiteProvider()
    inquiries = provider.list_inquiries()

    assert len(inquiries) >= 7
    companies = {i.company for i in inquiries if i.company}
    assert "Metroline Corp" in companies  # existing customer
    assert any("urgent" in i.subject.lower() for i in inquiries)
    assert any(i.company is None for i in inquiries)  # spam / no company given


def test_mock_website_provider_mark_processed():
    provider = MockWebsiteProvider()
    updated = provider.mark_processed("web_001")
    assert updated.status == "processed"
    assert provider.get_inquiry("web_001").status == "processed"
