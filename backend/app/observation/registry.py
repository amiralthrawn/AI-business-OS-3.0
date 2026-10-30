"""Observable Registry: the pluggable set of measurable signals the
Observation Engine knows how to compute, without the engine itself ever
needing to know anything about margin, delivery performance or customer
value specifically. Adding a new Observable (a new metric, a new domain)
never requires touching app.observation.engine -- only registering one more
entry here, reusing whatever Baseline-producing function already exists.
"""

# Needed because ObservableRegistry defines a method named `list`, which
# would otherwise shadow the builtin `list` for every annotation written
# after it in this class body (e.g. `for_entity_type`'s `-> list[Observable]`)
# once Python evaluates that annotation against the class's own namespace.
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from app.core.baseline import Baseline
from app.core.entities import BusinessContext, RelatedEntityType

# Same shape as app.core.baseline's margin_baseline / supplier_delivery_baseline
# / customer_value_baseline: takes a session, the entity id, and the company's
# BusinessContext (for a declared target), returns (Baseline, current_value).
ObservableCompute = Callable[[Session, uuid.UUID, "BusinessContext | None"], tuple[Baseline, float | None]]


ObservableExtraContext = Callable[[Session, uuid.UUID], dict]


@dataclass(frozen=True)
class Observable:
    """A named, measurable signal: which metric, which kind of entity it
    applies to, which existing Baseline function computes it, and the
    (medium, high) impact thresholds Significance should use for it -- in the
    metric's own unit, the same convention app.snapshot already used.

    `extra_context` is optional (step 22): a few Observables (e.g. an
    unanswered Communication's age) have one specific, concrete record worth
    attaching -- the actual message's subject/body -- so the Interpretation
    Engine's LLM has something more to reason about than a bare number.
    `None` for every Observable that has no such record (the original
    numeric-only metrics), producing an empty dict, exactly today's
    behavior -- purely additive, never required."""

    name: str
    domain: str
    entity_type: RelatedEntityType
    description: str
    compute: ObservableCompute
    impact_thresholds: tuple[float, float]
    extra_context: ObservableExtraContext | None = None


class ObservableRegistry:
    """Mirrors app.ai.capabilities.registry.CapabilityRegistry's shape on
    purpose: same "register once, look up by name, list them all" pattern
    already established for Capabilities."""

    def __init__(self) -> None:
        self._observables: dict[str, Observable] = {}

    def register(self, observable: Observable) -> None:
        if observable.name in self._observables:
            raise ValueError(f"Observable '{observable.name}' is already registered")
        self._observables[observable.name] = observable

    def get(self, name: str) -> Observable:
        try:
            return self._observables[name]
        except KeyError:
            raise KeyError(f"Unknown observable: '{name}'") from None

    def list(self) -> list[Observable]:
        return list(self._observables.values())

    def for_entity_type(self, entity_type: RelatedEntityType) -> list[Observable]:
        return [o for o in self._observables.values() if o.entity_type == entity_type]
