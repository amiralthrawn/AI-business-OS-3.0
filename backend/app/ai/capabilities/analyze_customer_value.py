import uuid

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.capabilities.base import Capability, CapabilityExecutionError
from app.core.analytics import compute_customer_value_trend
from app.core.entities import Customer
from app.core.events.bus import EventBus


class AnalyzeCustomerValueInput(BaseModel):
    customer_id: uuid.UUID


class AnalyzeCustomerValueOutput(BaseModel):
    customer_id: uuid.UUID
    sample_size: int
    baseline_revenue: float | None
    recent_revenue: float | None
    variation_pct: float | None
    trend: str


def _execute(session: Session, _event_bus: EventBus | None, data: AnalyzeCustomerValueInput) -> AnalyzeCustomerValueOutput:
    customer = session.get(Customer, data.customer_id)
    if customer is None:
        raise CapabilityExecutionError(f"Customer {data.customer_id} not found")

    result = compute_customer_value_trend(session, data.customer_id)
    return AnalyzeCustomerValueOutput(
        customer_id=data.customer_id,
        sample_size=result.sample_size,
        baseline_revenue=result.baseline_revenue,
        recent_revenue=result.recent_revenue,
        variation_pct=result.variation_pct,
        trend=result.trend,
    )


analyze_customer_value_capability = Capability(
    name="analyze_customer_value",
    description="Computes a Customer's revenue trend (growing/declining/stable) from real sales Transactions.",
    input_schema=AnalyzeCustomerValueInput,
    output_schema=AnalyzeCustomerValueOutput,
    requires_human_validation=False,
    executor=_execute,
)
