"""Response shape for the Sales domain overview (Step 23B). Composed
entirely from `app.data.service` (customer list, transactions) and
`HomeService.get_ai_priorities` -- no new business logic, no CRM pipeline,
no Deal entity, only a view over the existing Data Core.
"""

from pydantic import BaseModel

from app.data.schemas import CustomerListItem, IntelligenceSignal, MonthlyPointRead, TransactionRead


class SalesOverview(BaseModel):
    customer_count: int
    # From app.core.analytics.compute_company_financials -- reused, not recomputed.
    total_revenue: float
    customers: list[CustomerListItem]
    intelligence: list[IntelligenceSignal]
    recent_transactions: list[TransactionRead]
    # From app.core.analytics.compute_monthly_series -- real, zero-filled last 12 months.
    monthly_sales: list[MonthlyPointRead]
