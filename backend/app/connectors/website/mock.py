"""MockWebsiteProvider: realistic inbound inquiries from a company website
contact form. One inquiry deliberately comes from an existing customer
domain (Metroline Corp, matching data/seed.py) to demonstrate resolution
against the real Data Core; the rest are unresolved prospects or noise --
see brain/connectors.md.
"""

from datetime import datetime, timedelta, timezone

from app.connectors.models import WebsiteInquiry
from app.connectors.website.base import WebsiteProvider


def _seed_inquiries(now: datetime) -> list[WebsiteInquiry]:
    return [
        # 1. Commercial inquiry from a new prospect.
        WebsiteInquiry(
            external_id="web_001",
            name="Dana Whitfield",
            email="dana.whitfield@brookfieldindustrial.example",
            company="Brookfield Industrial",
            subject="Interested in a bulk supply partnership",
            message="We're looking for a new steel components supplier for a multi-year contract. Can we set up a call?",
            timestamp=now - timedelta(days=1, hours=2),
            source="contact_form",
        ),
        # 2. Quote request from an unknown prospect.
        WebsiteInquiry(
            external_id="web_002",
            name="Marco Duarte",
            email="marco@duartefab.example",
            company="Duarte Fabrication",
            subject="Quote request",
            message="Could you send a quote for 200 units of your standard steel bracket set?",
            timestamp=now - timedelta(hours=10),
            source="quote_form",
        ),
        # 3. General information request.
        WebsiteInquiry(
            external_id="web_003",
            name="Priya Nair",
            email="priya.nair@personalmail.example",
            company=None,
            subject="Product information",
            message="Do you publish technical datasheets for your hydraulic hose products?",
            timestamp=now - timedelta(hours=30),
            source="contact_form",
        ),
        # 4. Inquiry from an existing customer (domain matches Metroline Corp).
        WebsiteInquiry(
            external_id="web_004",
            name="Alex Renner",
            email="alex.renner@metrolinecorp.example",
            company="Metroline Corp",
            subject="Expanding our order volume",
            message="We'd like to discuss increasing our monthly order volume for Steel Frame Assembly -- who should we talk to?",
            # Deliberately old and never answered (step 22) -- so
            # customer_unanswered_message_age_days (app.observation, see
            # brain/external_data_intelligence.md) has a real signal to
            # detect for a known customer arriving through the website
            # channel specifically, not just email.
            timestamp=now - timedelta(days=9, hours=5),
            source="contact_form",
        ),
        # 5. Unknown prospect, cold outreach.
        WebsiteInquiry(
            external_id="web_005",
            name="Sam Okafor",
            email="sam.okafor@newventuretech.example",
            company="New Venture Tech",
            subject="Exploring suppliers for a new product line",
            message="We're launching a new product line and evaluating component suppliers. Can you share your catalog?",
            timestamp=now - timedelta(days=2),
            source="contact_form",
        ),
        # 6. Urgent request.
        WebsiteInquiry(
            external_id="web_006",
            name="Ines Faulkner",
            email="ines.faulkner@haldanemfg.example",
            company="Haldane Manufacturing",
            subject="URGENT -- production line down, need parts today",
            message="Our line is down waiting on a replacement part. Can someone call us back today?",
            timestamp=now - timedelta(hours=1),
            source="contact_form",
        ),
        # 7. Spam / irrelevant.
        WebsiteInquiry(
            external_id="web_007",
            name="SEO Growth Partners",
            email="offers@seogrowthpartners.example",
            company=None,
            subject="Boost your website ranking today!!!",
            message="We noticed your website could rank higher on Google. Ask us about our SEO packages.",
            timestamp=now - timedelta(days=3),
            source="contact_form",
        ),
    ]


class MockWebsiteProvider(WebsiteProvider):
    def __init__(self, now: datetime | None = None) -> None:
        self._inquiries: list[WebsiteInquiry] = _seed_inquiries(now or datetime.now(timezone.utc))

    def list_inquiries(self) -> list[WebsiteInquiry]:
        return list(self._inquiries)

    def get_inquiry(self, external_id: str) -> WebsiteInquiry | None:
        return next((i for i in self._inquiries if i.external_id == external_id), None)

    def mark_processed(self, external_id: str) -> WebsiteInquiry:
        inquiry = self.get_inquiry(external_id)
        if inquiry is None:
            raise KeyError(f"Unknown website inquiry: '{external_id}'")
        updated = WebsiteInquiry(**{**inquiry.__dict__, "status": "processed"})
        self._inquiries[self._inquiries.index(inquiry)] = updated
        return updated
