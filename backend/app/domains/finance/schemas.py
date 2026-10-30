"""Response shape for the Finance domain overview (Step 23B). Composed
entirely from `app.core.analytics` (company-wide totals, per-product margin
trend) and `app.data.schemas`/`app.data.service` (intelligence signals,
recent transactions) -- no new business logic, only a view that groups
existing numbers under the Finance domain.
"""

import uuid

from pydantic import BaseModel

from app.data.schemas import IntelligenceSignal, MonthlyPointRead, TransactionRead


class ProductMargin(BaseModel):
    id: uuid.UUID
    name: str
    # From app.core.analytics.compute_margin_trend -- reused, not recomputed.
    margin_trend: str
    recent_margin_pct: float | None


class FinanceOverview(BaseModel):
    # From app.core.analytics.compute_company_financials -- reused, not recomputed.
    total_revenue: float
    total_costs: float
    overall_margin_pct: float | None
    transaction_count: int
    products: list[ProductMargin]
    intelligence: list[IntelligenceSignal]
    recent_transactions: list[TransactionRead]
    # From app.core.analytics.compute_monthly_series -- real, zero-filled last 12 months.
    monthly_purchases: list[MonthlyPointRead]
    monthly_sales: list[MonthlyPointRead]
