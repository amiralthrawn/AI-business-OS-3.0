import uuid

from pydantic import BaseModel, Field

from app.data.schemas import IntelligenceSignal, MonthlyPointRead, SupplierListItem, TransactionRead


class ProcurementOverview(BaseModel):
    supplier_count: int
    # From app.core.analytics.compute_company_financials -- reused, not recomputed
    # (total spend is exactly its total_costs across the whole company).
    total_spend: float
    suppliers: list[SupplierListItem]
    intelligence: list[IntelligenceSignal]
    recent_transactions: list[TransactionRead]
    # From app.core.analytics.compute_monthly_series -- real, zero-filled last 12 months.
    monthly_purchases: list[MonthlyPointRead]


class SupplierCostChangeRequest(BaseModel):
    supplier_id: uuid.UUID
    product_id: uuid.UUID
    new_unit_cost: float = Field(gt=0)


class SupplierCostChangeResponse(BaseModel):
    event_id: uuid.UUID
    event_type: str
    correlation_id: uuid.UUID
    supplier_id: uuid.UUID
    product_id: uuid.UUID
    old_unit_cost: float
    new_unit_cost: float
    variation_pct: float
