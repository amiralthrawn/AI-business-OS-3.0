import pytest

from app.connectors.calendar.mock import MockCalendarProvider
from app.connectors.email.mock import MockEmailProvider
from app.connectors.registry import ConnectorRegistry, build_connector_registry
from app.connectors.website.mock import MockWebsiteProvider


def test_build_connector_registry_registers_the_three_mock_providers():
    registry = build_connector_registry()

    assert set(registry.list_connectors()) == {"email", "calendar", "website"}
    assert isinstance(registry.get_connector("email"), MockEmailProvider)
    assert isinstance(registry.get_connector("calendar"), MockCalendarProvider)
    assert isinstance(registry.get_connector("website"), MockWebsiteProvider)


def test_get_unknown_connector_raises():
    registry = build_connector_registry()

    with pytest.raises(KeyError):
        registry.get_connector("does_not_exist")


def test_registering_a_new_provider_does_not_require_touching_the_registry_class():
    """The point of the registry: swapping a provider (email -> a future
    GmailProvider) is exactly one register() call, no class changes."""

    registry = ConnectorRegistry()
    sentinel = object()
    registry.register("email", sentinel)

    assert registry.get_connector("email") is sentinel
