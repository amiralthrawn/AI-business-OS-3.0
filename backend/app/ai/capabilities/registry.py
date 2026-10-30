from app.ai.capabilities.base import Capability, CapabilityNotFoundError


class CapabilityRegistry:
    """Central lookup for every Capability the AI layer knows about. Agents
    reference capabilities by name and resolve them through the registry
    rather than importing capability modules directly, so adding a capability
    never requires touching an agent's import list."""

    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = {}

    def register(self, capability: Capability) -> None:
        if capability.name in self._capabilities:
            raise ValueError(f"Capability '{capability.name}' is already registered")
        self._capabilities[capability.name] = capability

    def get(self, name: str) -> Capability:
        try:
            return self._capabilities[name]
        except KeyError:
            raise CapabilityNotFoundError(name) from None

    def list(self) -> list[Capability]:
        return list(self._capabilities.values())
