"""WebsiteConnector interface: MockWebsiteProvider today, a real website
forms/CRM webhook integration later -- same interface, swapped in
app.connectors.registry without touching ingestion."""

from abc import ABC, abstractmethod

from app.connectors.models import WebsiteInquiry


class WebsiteProvider(ABC):
    @abstractmethod
    def list_inquiries(self) -> list[WebsiteInquiry]:
        """Every inquiry currently recorded, regardless of status."""

    @abstractmethod
    def get_inquiry(self, external_id: str) -> WebsiteInquiry | None:
        """A single inquiry by the provider's own id, or `None`."""

    @abstractmethod
    def mark_processed(self, external_id: str) -> WebsiteInquiry:
        """Marks an inquiry as processed at the source system -- closing the
        loop after ingestion, not a business decision about the inquiry."""
