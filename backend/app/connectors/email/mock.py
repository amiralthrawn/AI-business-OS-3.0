"""MockEmailProvider: a realistic, static in-memory mailbox standing in for
a real company inbox. Deliberately references the same supplier/customer
names `data/seed.py` creates (Northline Steel, BrightWorks Ltd, Metroline
Corp, Pacific Components, Coastal Metal Supply) so a sync against the real
seeded Data Core demonstrably resolves real Contacts to real Suppliers/
Customers -- see brain/connectors.md for why this coupling is intentional
and demo-only (the resolution logic itself, in app.connectors.ingestion, is
generic name matching, not hardcoded to these names).

Timestamps for the Northline/BrightWorks/Coastal messages (step 22) are
deliberately several days old and never answered, so
`supplier_unanswered_message_age_days`/`customer_unanswered_message_age_days`
(app.observation, see brain/external_data_intelligence.md) have a real,
material signal to detect end-to-end -- not tuned to any specific business
scenario, just old enough to cross the Observable's own impact thresholds.

No business logic here -- just data and the four EmailProvider methods.
"""

from datetime import datetime, timedelta, timezone

from app.connectors.email.base import EmailProvider
from app.connectors.models import ExternalEmail


def _seed_messages(now: datetime) -> list[ExternalEmail]:
    return [
        # 1. Supplier requesting a renegotiation.
        ExternalEmail(
            external_id="email_001",
            thread_id="thread_northline_pricing",
            sender="procurement@northlinesteel.com",
            recipients=["purchasing@acme.example"],
            subject="Steel pricing renegotiation",
            body=(
                "Hello, given recent raw material costs we would like to schedule a call to "
                "renegotiate pricing on the Steel Frame Assembly line for next quarter."
            ),
            timestamp=now - timedelta(days=8, hours=3),
            direction="inbound",
            status="unread",
        ),
        # 2. Customer reporting a delivery problem.
        ExternalEmail(
            external_id="email_002",
            thread_id="thread_brightworks_delivery",
            sender="ops@brightworks.co.uk",
            recipients=["support@acme.example"],
            subject="Late delivery on our last order",
            body=(
                "Our last shipment of Steel Frame Assembly arrived four days late, which pushed "
                "back our own production line. Can you confirm what happened?"
            ),
            timestamp=now - timedelta(days=9, hours=5),
            direction="inbound",
            status="unread",
        ),
        # 3. Unknown prospect requesting a quote.
        ExternalEmail(
            external_id="email_003",
            thread_id="thread_thornfield_quote",
            sender="sales@thornfieldindustries.example",
            recipients=["sales@acme.example"],
            subject="Quote request -- industrial fasteners",
            body="We are evaluating new suppliers for industrial fasteners. Could you send a quote for 5,000 units/month?",
            timestamp=now - timedelta(hours=14),
            direction="inbound",
            status="unread",
        ),
        # 4. Invoice sent (outbound).
        ExternalEmail(
            external_id="email_004",
            thread_id="thread_metroline_invoice",
            sender="billing@acme.example",
            recipients=["accounts@metrolinecorp.example"],
            subject="Invoice INV-2050",
            body="Please find attached invoice INV-2050 for last month's Steel Frame Assembly order.",
            timestamp=now - timedelta(days=3),
            attachments=["invoice_INV-2050.pdf"],
            direction="outbound",
            status="sent",
        ),
        # 5. Supplier contract nearing expiration.
        ExternalEmail(
            external_id="email_005",
            thread_id="thread_pacific_contract",
            sender="contracts@pacificcomponents.example",
            recipients=["procurement@acme.example"],
            subject="Supply agreement renewal -- expires in 30 days",
            body="This is a reminder that our current supply agreement expires in 30 days. Let us know if you'd like to renew.",
            timestamp=now - timedelta(hours=20),
            direction="inbound",
            status="unread",
        ),
        # 6. Unimportant email.
        ExternalEmail(
            external_id="email_006",
            thread_id="thread_newsletter",
            sender="newsletter@industryweekly.example",
            recipients=["contact@acme.example"],
            subject="This week in manufacturing",
            body="Your weekly roundup of manufacturing industry news.",
            timestamp=now - timedelta(days=4),
            direction="inbound",
            status="read",
        ),
        # 7. A second message from an already-seen sender (Northline Steel),
        # demonstrating Contact reuse across two messages from the same
        # external identity rather than creating a duplicate Contact.
        ExternalEmail(
            external_id="email_007",
            thread_id="thread_northline_pricing",
            sender="procurement@northlinesteel.com",
            recipients=["purchasing@acme.example"],
            subject="Re: Steel pricing renegotiation",
            body="Following up -- are you available for a call this Thursday?",
            timestamp=now - timedelta(hours=6),
            direction="inbound",
            status="unread",
        ),
        # 8. A new, thin-history supplier relationship (Coastal Metal
        # Supply, the same entity Step 16 used to demonstrate the "insight"
        # case) checking in about delivery scheduling -- never answered.
        # Unlike Northline/BrightWorks/Pacific, Coastal has no open Risk/
        # Opportunity from the older per-metric rules, so this is the one
        # entity where step 22's full loop (Observation -> Interpretation ->
        # Decision -> Action Proposal) isn't shadowed by an existing signal.
        ExternalEmail(
            external_id="email_008",
            thread_id="thread_coastal_logistics",
            sender="dispatch@coastalmetalsupply.example",
            recipients=["purchasing@acme.example"],
            subject="Question about our delivery schedule",
            body=(
                "We wanted to check in about adjusting our delivery schedule for the fastener "
                "kits -- do you have a few minutes this week to discuss?"
            ),
            timestamp=now - timedelta(days=9),
            direction="inbound",
            status="unread",
        ),
    ]


class MockEmailProvider(EmailProvider):
    def __init__(self, now: datetime | None = None) -> None:
        self._messages: list[ExternalEmail] = _seed_messages(now or datetime.now(timezone.utc))

    def list_messages(self) -> list[ExternalEmail]:
        return list(self._messages)

    def get_message(self, external_id: str) -> ExternalEmail | None:
        return next((m for m in self._messages if m.external_id == external_id), None)

    def search_messages(self, query: str) -> list[ExternalEmail]:
        lowered = query.lower()
        return [m for m in self._messages if lowered in m.subject.lower() or lowered in m.body.lower()]

    def send_message(
        self, *, recipients: list[str], subject: str, body: str, thread_id: str | None = None
    ) -> ExternalEmail:
        message = ExternalEmail(
            external_id=f"email_{len(self._messages) + 1:03d}",
            thread_id=thread_id or f"thread_{len(self._messages) + 1}",
            sender="me@acme.example",
            recipients=recipients,
            subject=subject,
            body=body,
            timestamp=datetime.now(timezone.utc),
            direction="outbound",
            status="sent",
        )
        self._messages.append(message)
        return message
