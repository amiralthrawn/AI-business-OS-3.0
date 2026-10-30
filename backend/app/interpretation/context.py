"""Context Assembly: builds the compact, relevant context an LLM needs to
interpret one ObservationDetected Business Event -- Business Context,
Baseline/Significance (already embedded in the Observation's own payload, not
recomputed), a Business State Snapshot summary, any correlated observations,
and, when the event alone isn't enough, the same targeted AI capabilities a
human's question about that entity would trigger.

Never loads the whole Data Core into the prompt: only the handful of fields
below, plus whatever the existing capability dispatch decides is relevant for
this entity -- exactly the same targeted set a named Ask AI question would
have used, reused rather than reimplemented (see
app.ai.orchestrator.service._dispatch_targeted_capabilities).
"""

import uuid

from sqlalchemy.orm import Session

from app.ai.agents import AGENTS
from app.ai.capabilities.registry import CapabilityRegistry
from app.ai.llm import LLMClient
from app.ai.orchestrator.service import AIOrchestrator, _TOPIC_AGENTS, _resolve_entity_by_ref
from app.business_context.service import BusinessContextService
from app.core.entities import EventLogEntry
from app.core.events.bus import EventBus
from app.snapshot.service import build_snapshot


def assemble_context(
    session: Session,
    event_bus: EventBus,
    capability_registry: CapabilityRegistry,
    llm: LLMClient,
    company_id: uuid.UUID,
    entry: EventLogEntry,
) -> tuple[dict, list[str]]:
    """Returns (context, capabilities_consulted). `capabilities_consulted` is
    empty when the Business Event's own payload already carried enough for
    the classification and narrative -- deeper capability calls only happen
    for a domain the Orchestrator's agents actually cover."""

    payload = entry.payload
    business_context = BusinessContextService(session).get_or_create(company_id)

    # A few Observables (step 22: external data) attach one specific,
    # concrete record -- e.g. the actual unanswered Communication's subject/
    # body -- so the LLM has something more to reason about than a bare
    # number. Empty for every Observable that doesn't register one (the
    # original numeric-only metrics), so this changes nothing for them.
    # When the message-bearing Observable ended up as the correlated one
    # rather than the primary (app.observation's own cross-domain
    # correlation), its extra is still surfaced, just under its own key.
    extra = payload.get("extra_context") or {}
    correlated_extras = [
        c.get("extra_context") for c in payload.get("correlated_observations", []) if c.get("extra_context")
    ]

    context: dict = {
        "business_event": {
            "event_type": entry.event_type,
            "source": entry.source,
            "observable": payload.get("observable"),
            "domain": payload.get("domain"),
            "entity_type": payload.get("entity_type"),
            "entity_name": payload.get("entity_name"),
            "current_value": payload.get("current_value"),
            "related_message": extra or None,
        },
        "baseline": {
            "reference_value": payload.get("baseline_reference_value"),
            "source": payload.get("baseline_source"),
            "confidence": payload.get("baseline_confidence"),
        },
        "significance": {
            "deviation": payload.get("deviation"),
            "impact": payload.get("impact"),
            "urgency": payload.get("urgency"),
            "recurrence_count": payload.get("recurrence_count"),
            "strategic_relevance": payload.get("strategic_relevance"),
        },
        "correlated_observations": payload.get("correlated_observations", []),
        "related_messages_from_correlated_observations": correlated_extras or None,
        "business_context": {
            "monitored_domains": business_context.monitored_domains,
            "stated_objectives": business_context.stated_objectives,
            "declared_baseline_for_this_metric": business_context.declared_baselines.get(
                payload.get("observable")
            ),
        },
    }

    snapshot = build_snapshot(session, company_id)
    context["snapshot_summary"] = {
        "open_risks_count": snapshot.open_risks_count,
        "open_opportunities_count": snapshot.open_opportunities_count,
        "material_areas_count": len(snapshot.material_areas),
    }

    capabilities_consulted: list[str] = []
    agents = [AGENTS[name] for name in _TOPIC_AGENTS.get(payload.get("domain"), ())]
    if agents:
        supplier, product, customer = _resolve_entity_by_ref(
            session, payload.get("entity_type"), payload.get("entity_id")
        )
        orchestrator = AIOrchestrator(session, capability_registry, llm, event_bus)
        capability_data: dict = {}
        orchestrator._dispatch_targeted_capabilities(
            agents, supplier, product, customer, capability_data, capabilities_consulted
        )
        if capability_data:
            context["capability_data"] = capability_data

    return context, capabilities_consulted
