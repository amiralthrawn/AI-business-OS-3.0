"""Connector Registry: mirrors app.ai.capabilities.registry.CapabilityRegistry's
shape on purpose -- register once, look up by connector type, list them all.
Replacing a provider later (email -> GmailProvider) means changing exactly
one `register()` call here; nothing above this module (ingestion, the
router) ever imports a concrete provider directly.
"""

from app.connectors.calendar.mock import MockCalendarProvider
from app.connectors.email.mock import MockEmailProvider
from app.connectors.website.mock import MockWebsiteProvider


class ConnectorRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, object] = {}

    def register(self, connector_type: str, provider: object) -> None:
        self._providers[connector_type] = provider

    def get_connector(self, connector_type: str) -> object:
        try:
            return self._providers[connector_type]
        except KeyError:
            raise KeyError(f"Unknown connector type: '{connector_type}'") from None

    def list_connectors(self) -> list[str]:
        return list(self._providers.keys())


def build_connector_registry() -> ConnectorRegistry:
    """Exposed as a function (rather than only the singleton below) so tests
    can build an isolated registry instead of depending on shared global
    state -- same pattern as build_capability_registry()."""

    registry = ConnectorRegistry()
    registry.register("email", MockEmailProvider())
    registry.register("calendar", MockCalendarProvider())
    registry.register("website", MockWebsiteProvider())
    return registry


connector_registry = build_connector_registry()
