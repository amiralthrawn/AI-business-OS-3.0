"""Normalized external objects: the one shape every provider (mock today,
a real Gmail/Outlook/Google Calendar provider later) must produce, so the
ingestion layer (app.connectors.ingestion) and everything above it never
has to know which provider an object came from.

Providers never write these into the Data Core themselves -- see
app.connectors.ingestion for the one place that maps a normalized object
onto Communication/Document/Contact rows.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class ExternalEmail:
    external_id: str
    thread_id: str
    sender: str
    recipients: list[str]
    subject: str
    body: str
    timestamp: datetime
    attachments: list[str] = field(default_factory=list)
    direction: Literal["inbound", "outbound"] = "inbound"
    status: Literal["unread", "read", "replied", "sent"] = "unread"


@dataclass(frozen=True)
class ExternalCalendarEvent:
    external_id: str
    title: str
    start: datetime
    end: datetime
    attendees: list[str] = field(default_factory=list)
    description: str | None = None
    location: str | None = None
    status: Literal["confirmed", "tentative", "cancelled"] = "confirmed"


@dataclass(frozen=True)
class WebsiteInquiry:
    external_id: str
    name: str
    email: str
    subject: str
    message: str
    timestamp: datetime
    company: str | None = None
    source: str = "contact_form"
    status: Literal["new", "processed"] = "new"
