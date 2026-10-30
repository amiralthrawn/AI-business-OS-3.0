import uuid
from datetime import datetime, timezone

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.capabilities.base import Capability
from app.core.entities import Company
from app.core.events.bus import EventBus
from app.snapshot.service import SnapshotArea, build_snapshot


class GetBusinessStateSnapshotInput(BaseModel):
    """No parameters: single-company MVP, same assumption Home and
    BusinessContext already make."""


class SnapshotAreaOutput(BaseModel):
    domain: str
    kind: str
    title: str
    entity_type: str | None
    entity_id: uuid.UUID | None
    metric: str | None
    current_value: float | None
    baseline_reference_value: float | None
    baseline_source: str | None
    baseline_confidence: str | None
    deviation: float | None
    impact: str
    urgency: str
    persistence: str
    recurrence_count: int
    correlation: list[str]
    strategic_relevance: str


class GetBusinessStateSnapshotOutput(BaseModel):
    generated_at: str
    monitored_domains: list[str]
    stated_objectives: str | None
    open_risks_count: int
    open_opportunities_count: int
    pending_validation_tasks: int
    material_areas: list[SnapshotAreaOutput]


def _dump_area(area: SnapshotArea) -> SnapshotAreaOutput:
    return SnapshotAreaOutput(
        domain=area.domain,
        kind=area.kind,
        title=area.title,
        entity_type=area.entity_type.value if area.entity_type else None,
        entity_id=area.entity_id,
        metric=area.metric,
        current_value=area.current_value,
        baseline_reference_value=area.baseline.reference_value if area.baseline else None,
        baseline_source=area.baseline.source if area.baseline else None,
        baseline_confidence=area.baseline.confidence if area.baseline else None,
        deviation=area.significance.deviation,
        impact=area.significance.impact,
        urgency=area.significance.urgency,
        persistence=area.significance.persistence,
        recurrence_count=area.significance.recurrence_count,
        correlation=area.significance.correlation,
        strategic_relevance=area.significance.strategic_relevance,
    )


def _execute(
    session: Session, _event_bus: EventBus | None, _data: GetBusinessStateSnapshotInput
) -> GetBusinessStateSnapshotOutput:
    company = session.query(Company).first()
    if company is None:
        # No company configured yet -- an empty snapshot, not an error, same
        # as list_priorities returning zeros on a fresh install.
        return GetBusinessStateSnapshotOutput(
            generated_at=datetime.now(timezone.utc).isoformat(),
            monitored_domains=[],
            stated_objectives=None,
            open_risks_count=0,
            open_opportunities_count=0,
            pending_validation_tasks=0,
            material_areas=[],
        )

    snapshot = build_snapshot(session, company.id)

    return GetBusinessStateSnapshotOutput(
        generated_at=snapshot.generated_at.isoformat(),
        monitored_domains=snapshot.monitored_domains,
        stated_objectives=snapshot.stated_objectives,
        open_risks_count=snapshot.open_risks_count,
        open_opportunities_count=snapshot.open_opportunities_count,
        pending_validation_tasks=snapshot.pending_validation_tasks,
        material_areas=[_dump_area(a) for a in snapshot.material_areas],
    )


get_business_state_snapshot_capability = Capability(
    name="get_business_state_snapshot",
    description="Compact, deterministic view of what currently matters across the business, ranked by significance.",
    input_schema=GetBusinessStateSnapshotInput,
    output_schema=GetBusinessStateSnapshotOutput,
    requires_human_validation=False,
    executor=_execute,
)
