"""The Observation Engine: sweeps every registered Observable over every
relevant entity, compares each to its Baseline, classifies the deviation with
Significance, groups cross-domain anomalies that describe the same underlying
phenomenon, and publishes one BusinessEvent per resulting phenomenon.

Deliberately generic: there is no per-event-type `if` branch here. The only
thing that knows "margin" or "delivery delay" means anything specific is the
Observable Registry (app.observation.registry); this module only knows how to
compute an Observation from whichever Observable it's given, decide whether
it's anomalous via the existing Significance machinery, and publish.

An anomalous Observation is not automatically a Risk or an Opportunity --
this engine stops at "ObservationDetected", a Business Event on the existing
Event Bus/Event Log. Turning that into a Risk/Opportunity/Insight is a later,
separate interpretation step (see brain/observation_engine.md), not something
this engine decides.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.business_context.service import BusinessContextService
from app.core.entities import BusinessContext, Customer, EventLogEntry, Product, RelatedEntityType, Supplier
from app.core.events.bus import EventBus
from app.core.events.business_event import BusinessEvent
from app.core.significance import Significance, assess_significance
from app.observation.registry import Observable, ObservableRegistry

OBSERVATION_DETECTED = "ObservationDetected"

_ENTITY_MODELS = {
    RelatedEntityType.SUPPLIER: Supplier,
    RelatedEntityType.PRODUCT: Product,
    RelatedEntityType.CUSTOMER: Customer,
}


@dataclass(frozen=True)
class Observation:
    """What was constated for one Observable on one entity -- not yet a
    business phenomenon, just a measurement compared to a baseline."""

    observable: str
    domain: str
    entity_type: RelatedEntityType
    entity_id: uuid.UUID
    entity_name: str
    current_value: float | None
    baseline_reference_value: float | None
    baseline_source: str
    baseline_confidence: str
    significance: Significance
    # Optional (step 22): a specific record worth attaching, e.g. the actual
    # unanswered Communication's subject/body -- {} for every Observable
    # that doesn't register an `extra_context` callback, exactly the prior
    # behavior. Never used for classification, only for the Interpretation
    # Engine's LLM narrative (see app.interpretation.context).
    extra_context: dict = field(default_factory=dict)

    @property
    def is_anomalous(self) -> bool:
        return self.significance.is_material


def _entity_name(session: Session, entity_type: RelatedEntityType, entity_id: uuid.UUID) -> str:
    model = _ENTITY_MODELS.get(entity_type)
    row = session.get(model, entity_id) if model is not None else None
    return getattr(row, "name", None) or str(entity_id)


def _matching_entries(session: Session, observable_name: str, entity_id: uuid.UUID) -> list[EventLogEntry]:
    target = str(entity_id)
    return [
        entry
        for entry in session.query(EventLogEntry).filter_by(event_type=OBSERVATION_DETECTED).all()
        if entry.payload.get("observable") == observable_name and entry.payload.get("entity_id") == target
    ]


def _strategic_relevance(business_context: BusinessContext, observable: Observable) -> str:
    objectives = (business_context.stated_objectives or "").lower()
    keyword = observable.name.split("_")[0]
    if observable.domain in objectives or keyword in objectives:
        return "high"
    if observable.domain in business_context.monitored_domains:
        return "medium"
    return "low"


def compute_observation(
    session: Session,
    observable: Observable,
    entity_id: uuid.UUID,
    business_context: BusinessContext,
) -> Observation:
    """Computes one Observation: Baseline (reused from app.core.baseline via
    the Observable's own `compute`) + Significance (reused from
    app.core.significance), never a second, parallel calculation."""

    baseline, current_value = observable.compute(session, entity_id, business_context)
    recurrence_count = len(_matching_entries(session, observable.name, entity_id))

    significance = assess_significance(
        baseline,
        current_value,
        impact_thresholds=observable.impact_thresholds,
        recurrence_count=recurrence_count,
        strategic_relevance=_strategic_relevance(business_context, observable),
    )

    return Observation(
        observable=observable.name,
        domain=observable.domain,
        entity_type=observable.entity_type,
        entity_id=entity_id,
        entity_name=_entity_name(session, observable.entity_type, entity_id),
        current_value=current_value,
        baseline_reference_value=baseline.reference_value,
        baseline_source=baseline.source,
        baseline_confidence=baseline.confidence,
        significance=significance,
        extra_context=observable.extra_context(session, entity_id) if observable.extra_context else {},
    )


def _correlate(session: Session, anomalies: list[Observation]) -> list[list[Observation]]:
    """Groups anomalous Observations that describe the same underlying
    phenomenon across domains. For this MVP, exactly one real link is
    followed -- a Product and its own Supplier (e.g. supplier cost/delivery
    trouble showing up as a product's margin/availability problem) -- rather
    than a general graph search. See brain/observation_engine.md."""

    clusters: list[list[Observation]] = []
    consumed: set[int] = set()

    for i, observation in enumerate(anomalies):
        if i in consumed:
            continue
        cluster = [observation]
        consumed.add(i)

        if observation.entity_type == RelatedEntityType.PRODUCT:
            product = session.get(Product, observation.entity_id)
            if product is not None and product.supplier_id is not None:
                for j, other in enumerate(anomalies):
                    if (
                        j not in consumed
                        and other.entity_type == RelatedEntityType.SUPPLIER
                        and other.entity_id == product.supplier_id
                    ):
                        cluster.append(other)
                        consumed.add(j)

        clusters.append(cluster)

    return clusters


def _observation_payload(observation: Observation) -> dict:
    return {
        "observable": observation.observable,
        "domain": observation.domain,
        "entity_type": observation.entity_type.value,
        "entity_id": str(observation.entity_id),
        "entity_name": observation.entity_name,
        "current_value": observation.current_value,
        "baseline_reference_value": observation.baseline_reference_value,
        "baseline_source": observation.baseline_source,
        "baseline_confidence": observation.baseline_confidence,
        "deviation": observation.significance.deviation,
        "impact": observation.significance.impact,
        "urgency": observation.significance.urgency,
        "recurrence_count": observation.significance.recurrence_count,
        "strategic_relevance": observation.significance.strategic_relevance,
        "extra_context": observation.extra_context,
    }


def run_observation_sweep(session: Session, event_bus: EventBus, registry: ObservableRegistry, company_id: uuid.UUID) -> dict:
    """Discovers, computes, correlates and publishes -- the one entry point a
    manual trigger (or, later, a scheduler) calls. Safe to call repeatedly:
    an already-published (observable, entity) pair is never republished."""

    business_context = BusinessContextService(session).get_or_create(company_id)

    observations: list[Observation] = []
    for observable in registry.list():
        model = _ENTITY_MODELS[observable.entity_type]
        for row in session.query(model).filter_by(company_id=company_id).all():
            observations.append(compute_observation(session, observable, row.id, business_context))

    anomalies = [o for o in observations if o.is_anomalous]
    clusters = _correlate(session, anomalies)

    published = 0
    for cluster in clusters:
        primary, *correlated = cluster
        if _matching_entries(session, primary.observable, primary.entity_id):
            continue  # already published in a previous sweep, still current

        payload = _observation_payload(primary)
        payload["correlated_observations"] = [_observation_payload(c) for c in correlated]

        event_bus.publish(BusinessEvent(event_type=OBSERVATION_DETECTED, source="observation_engine", payload=payload))
        published += 1

    return {
        "observations_computed": len(observations),
        "anomalies_detected": len(anomalies),
        "business_events_published": published,
    }
