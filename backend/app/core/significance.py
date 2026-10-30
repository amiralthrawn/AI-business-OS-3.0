"""Deterministic significance assessment: is this deviation worth surfacing,
and why? Deliberately NOT a single 0-100 score -- each dimension is kept
separate and inspectable, because "should a human see this" is a judgment
call best explained by several small, legible facts (how big, how urgent, has
it happened before, is it linked to something else, does it relate to a
stated priority) rather than compressed into one opaque number.

Used by the Business State Snapshot (app.snapshot) to rank and filter what
Intelligence has already found -- this module does not detect anything on its
own; it explains why something already flagged as a Risk/Opportunity does or
doesn't deserve attention right now.
"""

from dataclasses import dataclass, field
from typing import Literal

from app.core.baseline import Baseline

ImpactLevel = Literal["low", "medium", "high"]
UrgencyLevel = Literal["low", "medium", "high"]
Persistence = Literal["new", "ongoing", "recurring"]
Relevance = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class Significance:
    deviation: float | None  # current_value - baseline.reference_value, same unit as the metric
    impact: ImpactLevel
    urgency: UrgencyLevel
    persistence: Persistence
    recurrence_count: int
    correlation: list[str] = field(default_factory=list)
    strategic_relevance: Relevance = "low"
    confidence: str = "insufficient"  # mirrors Baseline.confidence

    @property
    def is_material(self) -> bool:
        """A simple, explainable gate for "does this deserve to surface at
        all" -- not a black-box aggregate score. Kept as one readable rule
        rather than a weighted formula so it stays auditable."""

        if self.impact == "high" or self.urgency == "high":
            return True
        if self.persistence == "recurring" and self.impact != "low":
            return True
        return False


def _classify_impact(deviation: float | None, *, medium_at: float, high_at: float) -> ImpactLevel:
    if deviation is None:
        return "low"
    magnitude = abs(deviation)
    if magnitude >= high_at:
        return "high"
    if magnitude >= medium_at:
        return "medium"
    return "low"


def _classify_urgency(impact: ImpactLevel, persistence: Persistence) -> UrgencyLevel:
    if impact == "high":
        return "high"
    if impact == "medium" and persistence != "new":
        return "high"
    if impact == "medium":
        return "medium"
    return "low"


def _classify_persistence(recurrence_count: int) -> Persistence:
    if recurrence_count <= 0:
        return "new"
    if recurrence_count == 1:
        return "ongoing"
    return "recurring"


def assess_significance(
    baseline: Baseline,
    current_value: float | None,
    *,
    impact_thresholds: tuple[float, float],
    recurrence_count: int = 0,
    correlation: list[str] | None = None,
    strategic_relevance: Relevance = "low",
) -> Significance:
    """Builds a Significance from a Baseline and the metric's current value.

    `impact_thresholds` is (medium_at, high_at) in the metric's own unit
    (e.g. margin points, days of delay, revenue variation) -- callers pass
    the same thresholds the existing Intelligence rules already use, so this
    does not introduce a second, competing set of severity cutoffs.
    """

    reference = baseline.reference_value
    deviation = current_value - reference if (current_value is not None and reference is not None) else None

    medium_at, high_at = impact_thresholds
    impact = _classify_impact(deviation, medium_at=medium_at, high_at=high_at)
    persistence = _classify_persistence(recurrence_count)
    urgency = _classify_urgency(impact, persistence)

    return Significance(
        deviation=deviation,
        impact=impact,
        urgency=urgency,
        persistence=persistence,
        recurrence_count=recurrence_count,
        correlation=correlation or [],
        strategic_relevance=strategic_relevance,
        confidence=baseline.confidence,
    )
