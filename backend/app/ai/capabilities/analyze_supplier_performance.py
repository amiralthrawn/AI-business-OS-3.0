import uuid

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.capabilities.base import Capability, CapabilityExecutionError
from app.core.analytics import compute_supplier_delivery_performance
from app.core.entities import Supplier
from app.core.events.bus import EventBus


class AnalyzeSupplierPerformanceInput(BaseModel):
    supplier_id: uuid.UUID


class AnalyzeSupplierPerformanceOutput(BaseModel):
    supplier_id: uuid.UUID
    sample_size: int
    baseline_avg_delay_days: float | None
    recent_avg_delay_days: float | None
    baseline_on_time_rate: float | None
    recent_on_time_rate: float | None
    trend: str


def _execute(
    session: Session, _event_bus: EventBus | None, data: AnalyzeSupplierPerformanceInput
) -> AnalyzeSupplierPerformanceOutput:
    supplier = session.get(Supplier, data.supplier_id)
    if supplier is None:
        raise CapabilityExecutionError(f"Supplier {data.supplier_id} not found")

    result = compute_supplier_delivery_performance(session, data.supplier_id)
    return AnalyzeSupplierPerformanceOutput(
        supplier_id=data.supplier_id,
        sample_size=result.sample_size,
        baseline_avg_delay_days=result.baseline_avg_delay_days,
        recent_avg_delay_days=result.recent_avg_delay_days,
        baseline_on_time_rate=result.baseline_on_time_rate,
        recent_on_time_rate=result.recent_on_time_rate,
        trend=result.trend,
    )


analyze_supplier_performance_capability = Capability(
    name="analyze_supplier_performance",
    description="Computes a Supplier's delivery performance trend (delay, on-time rate) from real Transactions.",
    input_schema=AnalyzeSupplierPerformanceInput,
    output_schema=AnalyzeSupplierPerformanceOutput,
    requires_human_validation=False,
    executor=_execute,
)
