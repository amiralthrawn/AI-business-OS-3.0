"""EmailConnector interface: MockEmailProvider today, a real GmailProvider/
OutlookProvider later -- same interface, swapped in app.connectors.registry
without touching ingestion or anything above it."""

from abc import ABC, abstractmethod

from app.connectors.models import ExternalEmail


class EmailProvider(ABC):
    @abstractmethod
    def list_messages(self) -> list[ExternalEmail]:
        """Every message currently visible to this mailbox."""

    @abstractmethod
    def get_message(self, external_id: str) -> ExternalEmail | None:
        """A single message by the provider's own id, or `None`."""

    @abstractmethod
    def search_messages(self, query: str) -> list[ExternalEmail]:
        """Messages whose subject or body contains `query` (case-insensitive)."""

    @abstractmethod
    def send_message(
        self, *, recipients: list[str], subject: str, body: str, thread_id: str | None = None
    ) -> ExternalEmail:
        """Sends a new outbound message. On the Mock Provider this only ever
        appends to its own in-memory mailbox -- no real email is ever sent."""
