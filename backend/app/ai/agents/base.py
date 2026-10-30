from dataclasses import dataclass

from app.ai.capabilities.base import Capability
from app.ai.capabilities.registry import CapabilityRegistry


@dataclass(frozen=True)
class Agent:
    """A bundle of capabilities plus a bit of specialized framing -- NOT a
    wrapper around a Business navigation domain. An agent only ever declares
    which capabilities it may use; it never creates its own tools, and the
    Orchestrator never calls a capability on its behalf that isn't listed
    here."""

    name: str
    description: str
    capability_names: tuple[str, ...]

    def capabilities(self, registry: CapabilityRegistry) -> list[Capability]:
        return [registry.get(name) for name in self.capability_names]
