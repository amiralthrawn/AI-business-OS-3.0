import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.actions.schemas import TaskRead
from app.core.entities.base import RelatedEntityType
from app.intelligence.opportunities.schemas import OpportunityRead
from app.intelligence.risks.schemas import RiskRead


class EventLogEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: uuid.UUID
    event_type: str
    source: str
    correlation_id: uuid.UUID
    occurred_at: datetime


class OverviewSummary(BaseModel):
    supplier_count: int
    product_count: int
    customer_count: int
    transaction_count: int


class RisksSummary(BaseModel):
    total_risks: int
    high_risks: int
    recent_risks: list[RiskRead]


class OpportunitiesSummary(BaseModel):
    total_opportunities: int
    recent_opportunities: list[OpportunityRead]


class TasksSummary(BaseModel):
    total_tasks: int
    pending_validation_tasks: int
    recent_tasks: list[TaskRead]


class AIPriorityRead(BaseModel):
    """One Business State Snapshot `material_area`, re-exposed as-is (see
    HomeService.get_ai_priorities) -- `kind` is the Snapshot's own vocabulary
    (risk/opportunity/observation/interpretation/decision), traceable back to
    its source; `interpretation_type` additionally carries the AI's own
    risk/opportunity/insight/observation judgment for interpretation/decision
    kinds. `detail_kind`/`detail_id` link back to an existing Risk/
    Opportunity detail page only when one exists -- `None` otherwise, never
    a broken or invented link."""

    kind: str
    interpretation_type: str | None
    domain: str
    title: str
    entity_type: RelatedEntityType | None
    entity_id: uuid.UUID | None
    impact: str
    urgency: str
    confidence: str
    explanation: str | None
    recommendation: str | None
    decision_options: list[dict] | None
    detail_kind: str | None
    detail_id: uuid.UUID | None


class DecisionRecommendationRead(BaseModel):
    chosen_option: str | None
    reasoning: str


class DecisionOptionRead(BaseModel):
    label: str
    expected_benefit: str
    trade_offs: str


class DecisionSummaryRead(BaseModel):
    """One `DecisionProposed` Event Log entry, re-hydrated as-is (see
    HomeService.get_decisions) -- no recomputation of options/recommendation/
    confidence, all already produced by app.decision.engine."""

    type: str
    problem: str
    domain: str
    entity_type: str | None
    entity_id: uuid.UUID | None
    options: list[DecisionOptionRead]
    recommendation: DecisionRecommendationRead
    confidence: str
    occurred_at: datetime


class OSActivityRead(BaseModel):
    """One Event Log entry translated into a short French business sentence
    (see HomeService.get_os_activity) -- never a raw event_type or payload."""

    event_type: str
    domain: str | None
    label: str
    detail: str
    occurred_at: datetime


class CompanyNarrativeItemRead(BaseModel):
    """One real Communication, close to as-is -- the raw material for "what
    actually happened" (see HomeService.get_company_narrative)."""

    id: uuid.UUID
    channel: str
    channel_detail: str | None
    direction: str
    subject: str | None
    body: str | None
    occurred_at: datetime
    related_entity_type: RelatedEntityType | None
    related_entity_name: str | None


class HomeResponse(BaseModel):
    overview: OverviewSummary
    priorities: list[AIPriorityRead]
    risks: RisksSummary
    opportunities: OpportunitiesSummary
    decisions: list[DecisionSummaryRead]
    tasks: TasksSummary
    recent_events: list[EventLogEntryRead]
    os_activity: list[OSActivityRead]
    company_narrative: list[CompanyNarrativeItemRead]
